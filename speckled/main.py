import asyncio
from typing import List, Literal, Union

from openai.types.chat import ChatCompletionMessageParam
from playwright.async_api import Browser, Page, async_playwright
from tarsier import Tarsier, GoogleVisionOCRService
import json

import base64
import instructor
from openai import OpenAI
from pydantic import BaseModel, Field
from config import config

system_prompt = """
    You are a test-automation agent. You can execute tests by driving a browser using the described instructions API.

    You are to issue instructions required to complete the test in as few steps as possible.

    You will initially be given the test specs description.

    You will then be passed a screenshot of the web page tagged with element IDs

    The element IDs are to the left of elements.

    The ID's have different prefixes to distinguish what type of elements they are:
        [#ID]: text-insertable fields (e.g. textarea, input with textual type)
        [@ID]: hyperlinks (<a> tags)
        [$ID]: other interactable elements (e.g. button, select)

    After receiving the web page content. You must respond with an instruction which will help you complete the test.
    You will then receive another screenshot and continue this process until you complete the test.

    If an instruction fails you will receive an error, to help you retry and correct your action.

    You will judge if the test has passed or failed based on the incoming screenshot.

    - You should only respond with with an action in order to drive your test browser and complete the test.
    - You should keep tests short using as few instruction as possible to complete a test.
"""

system_prompt_ocr = """
    You are a test-automation agent. You can execute tests by driving a browser using the described instructions API.

    You are to issue instructions required to complete the test in as few steps as possible.

    You will initially be given the test specs description.

    You will then be passed a text representation of the web page tagged with element IDs.

    The element IDs are to the left of elements.

    The ID's have different prefixes to distinguish what type of elements they are:
        [#ID]: text-insertable fields (e.g. textarea, input with textual type)
        [@ID]: hyperlinks (<a> tags)
        [$ID]: other interactable elements (e.g. button, select)

    After receiving the web page content. You must respond with an instruction which will help you complete the test.
    You will then receive another webpage content and continue this process until you complete the test.

    If an instruction fails you will receive an error, to help you retry and correct your action.

    You will judge if the test has passed or failed based on the incoming screenshot.

    - You should only respond with with an action in order to drive your test browser and complete the test.
    - You should keep tests short using as few instruction as possible to complete a test.
"""


class SpecResult(BaseModel):
    type: Literal["test_complete"]
    success: bool
    explanation: str


class Click(BaseModel):
    type: Literal["click", "double_click"]
    id: int


class TextInput(BaseModel):
    type: Literal["text_input"]
    id: int
    text: str


class KeyInput(BaseModel):
    type: Literal["single_key_input"]
    id: int
    key: str


class Message(BaseModel):
    Instruction: Union[Click, KeyInput, TextInput, SpecResult] = Field(
        ..., discriminator="type"
    )


client = instructor.from_openai(OpenAI(api_key=config.OPENAI_API_KEY))


def bytes_to_image_url(image: bytes):
    # Construct a base64 image
    base64_encoded_str = base64.b64encode(image).decode("utf-8")

    mime_type = "image/png"
    res = f"data:{mime_type};base64,{base64_encoded_str}"
    return res


def load_ocr_credentials(json_file_path):
    # To create the service account key, follow the instructions on this SO answer https://stackoverflow.com/a/46290808/1780891
    with open(json_file_path) as f:
        credentials = json.load(f)
    return credentials


class Agent:
    def __init__(self, browser: Browser) -> None:
        ocr_service = GoogleVisionOCRService(
            load_ocr_credentials("./service_account.json")
        )
        self.tarsier = Tarsier(ocr_service)
        self.browser = browser

    async def run_spec(self, spec_description: str, url: str):
        use_ocr = False 

        page = await self.browser.new_page()
        await page.goto(url)

        messages: List[ChatCompletionMessageParam] = []

        if use_ocr:
            messages.append({"role": "system", "content": system_prompt_ocr})
        else:
            messages.append({"role": "system", "content": system_prompt})

        messages.append(
            {"role": "user", "content": f"Spec description: {spec_description}"}
        )
        step_count = 0

        while True:
            step_count += 1

            if step_count > 10:
                raise Exception(f"Too many steps to execute spec: {spec_description}")

            if use_ocr:
                page_text, tag_to_xpath = await self.tarsier.page_to_text(page)
                print("---")
                print(page_text)
                print("---")

                messages.append(
                    {
                        "role": "user",
                        "content": page_text,
                    }
                )
            else:
                screenshot, tag_to_xpath = await self.tarsier.page_to_image(page)
                image_url = bytes_to_image_url(screenshot)

                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ],
                    }
                )

            message = await self.ask_llm(messages)

            if isinstance(message.Instruction, SpecResult):
                return message.Instruction

            # TODO: handle instruction errors
            try:
                await self.run_instruction(message, tag_to_xpath, page)
                messages.append(
                    {"role": "assistant", "content": message.model_dump_json()}
                )
            except Exception as e:
                print(tag_to_xpath)
                raise e

    async def run_instruction(self, message: Message, tag_to_xpath: dict, page: Page):
        instruction = message.Instruction

        print(f"running instruction: {instruction}")

        if isinstance(instruction, Click):
            x_path = tag_to_xpath[instruction.id]
            print("xpath: ", x_path)
            if instruction.type == "double_click":
                await page.locator(x_path).dblclick()
            else:
                await page.locator(x_path).click()

        if isinstance(instruction, KeyInput):
            x_path = tag_to_xpath[instruction.id]
            await page.locator(x_path).press(instruction.key)

        if isinstance(instruction, TextInput):
            x_path = tag_to_xpath[instruction.id]
            print("xpath: ", x_path)
            await page.locator(x_path).fill(instruction.text)
            # TODO: right now it's not great at knowing it should hit enter on some inputs
            # Investigate a way to remove .press("Enter")
            await page.locator(x_path).press("Enter")

        await page.wait_for_timeout(500)

    async def ask_llm(self, messages: List[ChatCompletionMessageParam]) -> Message:
        return client.chat.completions.create(
            model="gpt-4o",
            response_model=Message,
            messages=messages,
        )


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        agent = Agent(browser)

        result = await agent.run_spec(
            "Should be able to create and complete a TODO",
            "https://todomvc.com/examples/react/dist/#/",
        )
        print(result)


if __name__ == "__main__":
    asyncio.run(main())

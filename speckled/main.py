import asyncio

from playwright.async_api import Browser, async_playwright
from tarsier import Tarsier, GoogleVisionOCRService
import json


def load_ocr_credentials(json_file_path):
    with open(json_file_path) as f:
        credentials = json.load(f)
    return credentials


async def main():
    # To create the service account key, follow the instructions on this SO answer https://stackoverflow.com/a/46290808/1780891
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        agent = Agent(browser)
        result = await agent.run_spec(
            "Should be able to create a TODO",
            "https://todomvc.com/examples/react/dist/#/",
        )
        print(result)


class Agent:
    def __init__(self, browser: Browser) -> None:
        ocr_service = GoogleVisionOCRService(
            load_ocr_credentials("./service_account.json")
        )
        self.tarsier = Tarsier(ocr_service)
        self.browser = browser

    async def run_spec(self, spec_description: str, url: str):
        page = await self.browser.new_page()
        await page.goto("https://todomvc.com/examples/react/dist/#/")

        page_text, tag_to_xpath = await self.tarsier.page_to_text(page)
        return page_text


if __name__ == "__main__":
    asyncio.run(main())

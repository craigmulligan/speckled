import asyncio

from playwright.async_api import async_playwright
from tarsier import Tarsier, GoogleVisionOCRService
import json


def load_ocr_credentials(json_file_path):
    with open(json_file_path) as f:
        credentials = json.load(f)
    return credentials


async def main():
    # To create the service account key, follow the instructions on this SO answer https://stackoverflow.com/a/46290808/1780891

    ocr_service = GoogleVisionOCRService(load_ocr_credentials("./service_account.json"))

    tarsier = Tarsier(ocr_service)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("https://news.ycombinator.com")

        page_text, tag_to_xpath = await tarsier.page_to_text(page)

        print(tag_to_xpath)  # Mapping of tags to x_paths
        print(page_text)  # My Text representation of the page


if __name__ == "__main__":
    asyncio.run(main())

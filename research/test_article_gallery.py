"""Verify archived bytes, exact prompts, and the offline five-image selector."""

import hashlib
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/articles/selection-generations"


def test_gallery() -> None:
    """Exercise the generated artifact without contacting Docker or external services."""
    records = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    for row in records:
        assert hashlib.sha256((OUTPUT / row["file"]).read_bytes()).hexdigest() == row["sha256"]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto((OUTPUT / "index.html").as_uri())
        assert page.locator("article").count() == 18
        assert page.locator("img").evaluate_all("items => items.every(i => i.complete && i.naturalWidth > 0)")
        for row in records:
            if 4 <= row["number"] <= 21:
                card = page.locator(f"#G{row['number']:03d}")
                assert card.locator(".brief").text_content() == row["brief"]
                assert card.locator("img").get_attribute("src") == row["file"]
        boxes = page.locator('input[type="checkbox"]')
        for number in range(5):
            boxes.nth(number).check()
        assert boxes.nth(5).is_disabled()
        assert page.locator("#download").is_enabled()
        with page.expect_download() as download_info:
            page.locator("#download").click()
        selection = json.loads(Path(download_info.value.path()).read_text(encoding="utf-8"))
        assert [row["id"] for row in selection] == [f"G{number:03d}" for number in range(4, 9)]
        boxes.nth(0).uncheck()
        assert boxes.nth(5).is_enabled()
        assert page.locator("#download").is_disabled()
        for number in range(1, 5):
            boxes.nth(number).uncheck()
        page.screenshot(path=str(OUTPUT / "gallery-preview.png"))
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not errors, errors
        browser.close()
    print("PASS: 94 hashes, 18 exact image/brief pairs, images, max-five selector, JSON download, mobile layout")


if __name__ == "__main__":
    test_gallery()

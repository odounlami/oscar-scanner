import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

URL = "https://www.emploibenin.com/recherche-jobs-benin/informatique"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={"width": 1366, "height": 900},
            locale="fr-FR",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/152.0.0.0 Safari/537.36"
            ),
        )

        print("=== PLAYWRIGHT TEST ===")
        try:
            response = await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            print("initial_status:", response.status if response else None)
            print("final_url:", page.url)

            try:
                await page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                print("networkidle: timeout (continuing)")

            await page.wait_for_timeout(5000)

            print("title:", await page.title())
            print("content_length:", len(await page.content()))
            print("body_text_start:", (await page.locator("body").inner_text())[:1000].replace("\n", " | "))

            html = await page.content()
            Path("emploibenin_playwright.html").write_text(html, encoding="utf-8")
            await page.screenshot(path="emploibenin_playwright.png", full_page=True)

            print("html_saved: emploibenin_playwright.html")
            print("screenshot_saved: emploibenin_playwright.png")

            # Useful diagnostics for the next extraction step.
            print("links:", await page.locator("a").count())
            print("articles:", await page.locator("article").count())
            print("h2:", await page.locator("h2").count())
            print("h3:", await page.locator("h3").count())
            print("job-like classes:", await page.locator('[class*="job"], [class*="offer"], [class*="offre"]').count())

        except Exception as exc:
            print(type(exc).__name__, exc)
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())

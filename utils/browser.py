"""
utils/browser.py
Playwright browser automation — Microsoft Teams login and page interaction.
"""

import asyncio
from pathlib import Path
from loguru import logger
from core.config import cfg

SESSION_FILE = Path(__file__).parent.parent / "outputs" / "ms_session.json"


class Browser:
    """
    Manages a persistent Playwright browser session for Teams.
    Usage:
        from utils.browser import browser
        async with browser.page() as page:
            await page.goto("https://teams.microsoft.com")
    """

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None

    async def _launch(self):
        from playwright.async_api import async_playwright
        if self._browser:
            return
        pw = await async_playwright().start()
        self._playwright = pw
        self._browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        # Load saved session if exists
        storage = SESSION_FILE if SESSION_FILE.exists() else None
        self._context = await self._browser.new_context(
            storage_state=str(storage) if storage else None,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        logger.info("Browser launched")

    async def login_microsoft(self) -> bool:
        """Login to Microsoft and save session for reuse."""
        await self._launch()
        page = await self._context.new_page()
        try:
            await page.goto("https://login.microsoftonline.com/", timeout=30000)
            await page.fill("input[type='email']", cfg.ms_email)
            await page.click("input[type='submit']")
            await page.wait_for_selector("input[type='password']", timeout=10000)
            await page.fill("input[type='password']", cfg.ms_password)
            await page.click("input[type='submit']")
            # Handle "Stay signed in?" prompt
            try:
                await page.wait_for_selector("input[type='submit']", timeout=5000)
                await page.click("input[type='submit']")
            except Exception:
                pass
            # Save session
            await self._context.storage_state(path=str(SESSION_FILE))
            logger.info("Microsoft login successful — session saved")
            return True
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
        finally:
            await page.close()

    async def get_teams_assignments(self) -> list[dict]:
        """Navigate Teams and scrape assignment notifications."""
        await self._launch()
        page = await self._context.new_page()
        assignments = []
        try:
            await page.goto("https://teams.microsoft.com", timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=15000)
            # Look for assignment cards in activity feed
            cards = await page.query_selector_all("[data-tid='assignment-card'], .ts-assignment")
            for card in cards:
                text = await card.inner_text()
                if text.strip():
                    assignments.append({"source": "teams", "raw_text": text.strip()})
            logger.info(f"Found {len(assignments)} potential assignments in Teams")
        except Exception as e:
            logger.error(f"Teams scrape failed: {e}")
        finally:
            await page.close()
        return assignments

    async def submit_assignment(self, submit_url: str, file_path: str) -> bool:
        """Upload and submit an assignment file on Teams."""
        await self._launch()
        page = await self._context.new_page()
        try:
            await page.goto(submit_url, timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=15000)
            # Attach file
            file_input = await page.query_selector("input[type='file']")
            if file_input:
                await file_input.set_input_files(file_path)
                await asyncio.sleep(2)
            # Click submit button
            submit_btn = await page.query_selector("button:has-text('Turn in'), button:has-text('Submit')")
            if submit_btn:
                await submit_btn.click()
                await asyncio.sleep(2)
                logger.info(f"Assignment submitted via Playwright: {file_path}")
                return True
            logger.warning("Submit button not found")
            return False
        except Exception as e:
            logger.error(f"Submission failed: {e}")
            return False
        finally:
            await page.close()

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed")


browser = Browser()

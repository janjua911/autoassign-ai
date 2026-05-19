"""
agents/watcher.py
Watcher Agent — polls Microsoft Teams for new assignments.
Entry point called by scheduler every N minutes.
"""

import asyncio
from loguru import logger
from core.database import db
from core.memory import memory
from utils.browser import browser


class WatcherAgent:
    """
    Monitors Teams for new assignment notifications.
    Detected assignments are handed off to ExtractorAgent.
    """

    def __init__(self):
        self._seen_hashes: set = set(memory.get("seen_hashes", []))

    def _hash(self, text: str) -> str:
        import hashlib
        return hashlib.md5(text.strip().encode()).hexdigest()

    def run(self) -> list[int]:
        """
        Sync entry point — runs async browser code in a loop.
        Returns list of new assignment IDs created.
        """
        try:
            return asyncio.get_event_loop().run_until_complete(self._async_run())
        except RuntimeError:
            # No event loop in this thread — create one
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(self._async_run())
            loop.close()
            return result

    async def _async_run(self) -> list[int]:
        logger.info("WatcherAgent: Checking Teams for new assignments...")
        new_ids = []

        raw_items = await browser.get_teams_assignments()

        for item in raw_items:
            raw_text = item.get("raw_text", "").strip()
            if not raw_text:
                continue

            h = self._hash(raw_text)
            if h in self._seen_hashes:
                continue  # Already processed

            # Quick pre-filter — does it look like an assignment?
            keywords = ["assignment", "submit", "deadline", "due", "task", "quiz", "lab"]
            if not any(kw in raw_text.lower() for kw in keywords):
                logger.debug("Skipping non-assignment content")
                self._seen_hashes.add(h)
                continue

            # Create DB record
            assignment_id = db.create_assignment(
                title="Pending extraction",
                source=item.get("source", "teams"),
                raw_text=raw_text,
            )
            db.set_status(assignment_id, "detected")
            new_ids.append(assignment_id)
            self._seen_hashes.add(h)
            logger.info(f"New assignment detected → ID #{assignment_id}")

        # Persist seen hashes
        memory.set("seen_hashes", list(self._seen_hashes))
        logger.info(f"WatcherAgent done — {len(new_ids)} new assignment(s)")
        return new_ids


watcher_agent = WatcherAgent()

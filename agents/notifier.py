"""
agents/notifier.py
Notifier Agent — sends WhatsApp message with Drive link for student review.
"""

from loguru import logger
from core.database import db
from utils.whatsapp import whatsapp


class NotifierAgent:
    """
    Sends the approval request to the student via WhatsApp.
    Student replies YES to submit, or it auto-submits after timeout.
    """

    def run(self, assignment_id: int) -> bool:
        """Send WhatsApp notification. Returns True on success."""
        record = db.get(assignment_id)
        if not record:
            logger.error(f"NotifierAgent: Assignment #{assignment_id} not found")
            return False

        drive_link = record.get("drive_link", "")
        if not drive_link:
            logger.error(f"NotifierAgent: No Drive link for #{assignment_id}")
            return False

        subject = record.get("subject", "Unknown Subject")
        deadline = record.get("deadline", "Check Teams")
        confidence = record.get("confidence", 0)

        logger.info(f"NotifierAgent: Sending WhatsApp for #{assignment_id}")

        ok = whatsapp.send_assignment_ready(
            subject=subject,
            deadline=deadline,
            drive_link=drive_link,
            confidence=confidence,
        )

        if ok:
            db.set_status(assignment_id, "notified", "WhatsApp sent")
            logger.info(f"NotifierAgent done — notification sent")
        else:
            logger.warning("WhatsApp send failed — will still auto-submit on timeout")
            db.log(assignment_id, "notify_failed", "WhatsApp send returned False")

        return ok


notifier_agent = NotifierAgent()

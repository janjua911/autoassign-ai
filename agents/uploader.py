"""
agents/uploader.py
Uploader Agent — uploads PDF to Google Drive and saves the shareable link.
"""

from loguru import logger
from core.database import db
from utils.drive import drive


class UploaderAgent:
    """
    Takes the generated PDF and uploads it to Google Drive.
    Returns a shareable link stored in the assignment record.
    """

    def run(self, assignment_id: int) -> str:
        """
        Upload PDF to Drive.
        Returns shareable link, or "" on failure.
        """
        record = db.get(assignment_id)
        if not record:
            logger.error(f"UploaderAgent: Assignment #{assignment_id} not found")
            return ""

        pdf_path = record.get("pdf_path", "")
        if not pdf_path:
            logger.error(f"UploaderAgent: No PDF path for #{assignment_id}")
            db.set_status(assignment_id, "error", "No PDF to upload")
            return ""

        title = record.get("title", f"Assignment_{assignment_id}")
        subject = record.get("subject", "General")
        filename = f"{subject}_{title}.pdf".replace(" ", "_")[:80]

        logger.info(f"UploaderAgent: Uploading '{filename}' to Drive...")

        link = drive.upload(pdf_path, filename)

        if link:
            db.update(assignment_id, drive_link=link, status="drive_uploaded")
            db.log(assignment_id, "uploaded", link)
            logger.info(f"UploaderAgent done — {link}")
        else:
            db.set_status(assignment_id, "error", "Drive upload failed")

        return link


uploader_agent = UploaderAgent()

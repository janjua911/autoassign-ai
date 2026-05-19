"""
agents/extractor.py
Extractor Agent — parses raw assignment text into structured data using Groq.
"""

from loguru import logger
from core.database import db
from core.groq_client import groq_client


class ExtractorAgent:
    """
    Takes raw text from Teams/email and extracts:
    - Assignment title
    - Subject/course name
    - Deadline
    - List of questions
    - Special instructions
    - Confidence score
    """

    def run(self, assignment_id: int) -> bool:
        """
        Extract structured info from a detected assignment.
        Returns True on success.
        """
        record = db.get(assignment_id)
        if not record:
            logger.error(f"ExtractorAgent: Assignment #{assignment_id} not found")
            return False

        raw_text = record.get("raw_text", "")
        if not raw_text:
            db.set_status(assignment_id, "error", "No raw text to extract from")
            return False

        logger.info(f"ExtractorAgent: Extracting assignment #{assignment_id}")

        try:
            info = groq_client.extract_assignment_info(raw_text)
        except Exception as e:
            logger.error(f"Groq extraction failed: {e}")
            db.set_status(assignment_id, "error", str(e))
            return False

        # Validate confidence
        confidence = info.get("confidence", 0)
        if confidence < 40:
            logger.warning(
                f"Low confidence ({confidence}%) — skipping assignment #{assignment_id}"
            )
            db.set_status(assignment_id, "skipped", f"Low confidence: {confidence}%")
            return False

        # Persist extracted data
        db.update(
            assignment_id,
            title=info.get("title", "Untitled Assignment"),
            subject=info.get("subject", "General"),
            deadline=info.get("deadline", "Unknown"),
            questions=info.get("questions", [raw_text]),
            confidence=confidence,
            status="extracted",
        )
        db.log(assignment_id, "extracted",
               f"Title: {info.get('title')} | Questions: {len(info.get('questions', []))}")
        logger.info(
            f"ExtractorAgent done — #{assignment_id}: '{info.get('title')}' "
            f"({len(info.get('questions', []))} questions, confidence={confidence}%)"
        )
        return True


extractor_agent = ExtractorAgent()

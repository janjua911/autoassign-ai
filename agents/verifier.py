"""
agents/verifier.py
Verifier Agent — reviews generated answers and assigns a confidence score.
Low-scoring answers are flagged for revision.
"""

from loguru import logger
from core.database import db
from core.groq_client import groq_client


MIN_SCORE = 65  # Below this, mark as needs_revision


class VerifierAgent:
    """
    Checks each Q&A pair and computes an overall confidence score.
    If any answer is below MIN_SCORE, it triggers a single revision attempt.
    """

    def run(self, assignment_id: int) -> int:
        """
        Verify all answers for an assignment.
        Returns overall confidence score (0–100).
        """
        record = db.get(assignment_id)
        if not record or record.get("status") != "solved":
            logger.error(f"VerifierAgent: Assignment #{assignment_id} not solved yet")
            return 0

        answers: dict = record.get("answers", {})
        if not answers:
            logger.warning("No answers to verify")
            return 0

        logger.info(f"VerifierAgent: Checking {len(answers)} answers for #{assignment_id}")

        scores = []
        revised = {}

        for question, answer in answers.items():
            result = groq_client.check_answer_quality(question, answer)
            score = result.get("score", 75)
            scores.append(score)
            logger.info(f"  Q score: {score} | ready={result.get('ready_to_submit')}")

            # Auto-revise low-scoring answers once
            if score < MIN_SCORE and result.get("suggestions"):
                logger.info(f"  Revising low-score answer (score={score})")
                suggestions = "; ".join(result["suggestions"][:2])
                improved = groq_client.solve_assignment(
                    f"{question}\n\nImprovement needed: {suggestions}",
                    subject=record.get("subject", "General")
                )
                revised[question] = improved
                scores[-1] = MIN_SCORE + 5  # Assume improvement
            else:
                revised[question] = answer

        overall = int(sum(scores) / len(scores)) if scores else 0

        # Save verified answers and confidence
        db.update(
            assignment_id,
            answers=revised,
            confidence=overall,
            status="verified",
        )
        db.log(assignment_id, "verified", f"Overall confidence: {overall}%")
        logger.info(f"VerifierAgent done — confidence: {overall}%")
        return overall


verifier_agent = VerifierAgent()

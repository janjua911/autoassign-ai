"""
agents/solver.py
Solver Agent — generates answers for each question using Groq.
"""

from loguru import logger
from core.database import db
from core.groq_client import groq_client


class SolverAgent:
    """
    Iterates through the planner's question list and generates answers.
    Uses coding model for code questions, primary model for everything else.
    """

    def run(self, assignment_id: int, plan: list[dict]) -> dict[str, str]:
        """
        Solve all questions in the plan.
        Returns dict: {question_text: answer_text}
        """
        record = db.get(assignment_id)
        if not record:
            logger.error(f"SolverAgent: Assignment #{assignment_id} not found")
            return {}

        subject = record.get("subject", "General")
        answers = {}

        logger.info(f"SolverAgent: Solving {len(plan)} questions for #{assignment_id}")

        for item in plan:
            question = item["question"]
            q_type = item.get("type", "theory")
            word_target = item.get("word_target", 300)

            logger.info(f"Solving Q{item['index']+1} [{q_type}]: {question[:60]}...")

            try:
                if q_type == "code":
                    answer = groq_client.code(
                        f"Subject: {subject}\n\nQuestion: {question}\n\n"
                        f"Write a complete, well-commented solution."
                    )
                else:
                    answer = groq_client.solve_assignment(question, subject)

                answers[question] = answer
                logger.info(f"  ✓ Q{item['index']+1} solved ({len(answer.split())} words)")

            except Exception as e:
                logger.error(f"  ✗ Q{item['index']+1} failed: {e}")
                answers[question] = f"[Error solving this question: {e}]"

        # Persist answers
        db.update(assignment_id, answers=answers, status="solved")
        db.log(assignment_id, "solved", f"{len(answers)}/{len(plan)} questions answered")
        logger.info(f"SolverAgent done — {len(answers)} answers generated")
        return answers


solver_agent = SolverAgent()

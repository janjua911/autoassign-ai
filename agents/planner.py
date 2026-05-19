"""
agents/planner.py
Planner Agent — decides how to solve each question (text, code, math, etc.)
and orders questions by difficulty.
"""

import json
from loguru import logger
from core.database import db
from core.groq_client import groq_client


class PlannerAgent:
    """
    Analyzes extracted questions and builds a solve plan:
    - Categorizes each question (theory / code / math / diagram)
    - Estimates word count target
    - Sets solve order
    """

    def run(self, assignment_id: int) -> list[dict]:
        """
        Build a solve plan for an extracted assignment.
        Returns a list of plan items — one per question.
        """
        record = db.get(assignment_id)
        if not record or record.get("status") != "extracted":
            logger.error(f"PlannerAgent: Assignment #{assignment_id} not ready")
            return []

        questions = record.get("questions", [])
        subject = record.get("subject", "General")

        if not questions:
            logger.warning(f"No questions found in #{assignment_id}")
            return []

        logger.info(f"PlannerAgent: Planning {len(questions)} questions for #{assignment_id}")

        plan = []
        for i, question in enumerate(questions):
            q_type = self._classify_question(question, subject)
            plan.append({
                "index": i,
                "question": question,
                "type": q_type,
                "word_target": self._word_target(q_type),
                "subject": subject,
            })

        db.update(assignment_id, status="planned")
        db.log(assignment_id, "planned", f"{len(plan)} questions categorized")
        logger.info(f"PlannerAgent done — plan: {[p['type'] for p in plan]}")
        return plan

    def _classify_question(self, question: str, subject: str) -> str:
        prompt = f"""Classify this assignment question into ONE category:
- theory: explanation, definition, comparison, essay
- code: write program, function, script
- math: calculation, formula, numerical answer
- diagram: draw, design, model

Question: {question}
Subject: {subject}

Reply with ONLY one word: theory, code, math, or diagram"""
        try:
            result = groq_client.chat(prompt, max_tokens=10).strip().lower()
            if result in ("theory", "code", "math", "diagram"):
                return result
        except Exception:
            pass
        return "theory"

    def _word_target(self, q_type: str) -> int:
        return {"theory": 300, "code": 150, "math": 200, "diagram": 100}.get(q_type, 250)


planner_agent = PlannerAgent()

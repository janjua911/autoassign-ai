"""
agents/approval.py
Approval Agent — waits for student YES reply or auto-submits on timeout.
In Phase 1 this polls memory for approval flags set by an incoming webhook.
"""

import time
from datetime import datetime, timedelta
from loguru import logger
from core.database import db
from core.memory import memory
from core.config import cfg


class ApprovalAgent:
    """
    Manages the approval window for a notified assignment.

    Flow:
    1. Record approval start time
    2. Poll for "approved_{id}" key in memory (set by webhook/manual)
    3. If YES received → trigger submission
    4. If timeout reached and auto_submit=True → trigger submission
    5. If timeout reached and auto_submit=False → mark as expired

    In Phase 1, manually call:
        memory.set("approved_5", True)  # Approve assignment #5
    """

    def start_approval_window(self, assignment_id: int) -> None:
        """Record when approval window opened."""
        deadline = (
            datetime.now() + timedelta(minutes=cfg.approval_timeout)
        ).isoformat()
        memory.set(f"approval_deadline_{assignment_id}", deadline)
        db.log(assignment_id, "approval_started",
               f"Timeout: {cfg.approval_timeout}min — deadline: {deadline}")
        logger.info(f"Approval window opened for #{assignment_id} (timeout: {cfg.approval_timeout}min)")

    def check_approval(self, assignment_id: int) -> str:
        """
        Check current approval status.
        Returns: 'approved' | 'timeout' | 'waiting'
        """
        # Check manual approval flag
        if memory.get(f"approved_{assignment_id}"):
            return "approved"

        # Check timeout
        deadline_str = memory.get(f"approval_deadline_{assignment_id}")
        if deadline_str:
            deadline = datetime.fromisoformat(deadline_str)
            if datetime.now() > deadline:
                return "timeout"

        return "waiting"

    def process(self, assignment_id: int) -> str:
        """
        Evaluate approval status and update DB accordingly.
        Returns: 'approved' | 'auto_submitted' | 'expired' | 'waiting'
        """
        status = self.check_approval(assignment_id)

        if status == "approved":
            memory.delete(f"approved_{assignment_id}")
            memory.delete(f"approval_deadline_{assignment_id}")
            db.set_status(assignment_id, "approved", "Student replied YES")
            logger.info(f"Assignment #{assignment_id} approved by student")
            return "approved"

        elif status == "timeout":
            memory.delete(f"approval_deadline_{assignment_id}")
            if cfg.auto_submit:
                db.set_status(assignment_id, "approved", "Auto-approved on timeout")
                logger.info(f"Assignment #{assignment_id} auto-approved (timeout)")
                return "auto_submitted"
            else:
                db.set_status(assignment_id, "expired", "Approval timeout, auto_submit=false")
                logger.warning(f"Assignment #{assignment_id} expired — no approval received")
                return "expired"

        return "waiting"

    def approve_manually(self, assignment_id: int) -> None:
        """Manually approve an assignment (e.g. from dashboard or CLI)."""
        memory.set(f"approved_{assignment_id}", True)
        logger.info(f"Manual approval set for #{assignment_id}")


approval_agent = ApprovalAgent()

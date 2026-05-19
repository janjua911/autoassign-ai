"""
main.py
AutoAssign AI — Main orchestrator.
Starts the scheduler and runs the full pipeline for each detected assignment.

Run: python3 main.py
"""

import sys
import time
import signal
from pathlib import Path
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich import print as rprint

from core.config import cfg
from core.database import db
from core.memory import memory
from core.scheduler import scheduler

from agents.watcher import watcher_agent
from agents.extractor import extractor_agent
from agents.planner import planner_agent
from agents.solver import solver_agent
from agents.verifier import verifier_agent
from agents.doc_generator import doc_generator_agent
from agents.uploader import uploader_agent
from agents.notifier import notifier_agent
from agents.approval import approval_agent

console = Console()

# ── Logging setup ────────────────────────────────────────────

def setup_logging():
    log_file = Path(cfg._get("logging", "log_file", default="logs/autoassign.log"))
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level=cfg._get("logging", "level", default="INFO"),
               format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
    if cfg._get("logging", "log_to_file", default=True):
        logger.add(str(log_file), rotation="10 MB", retention="7 days",
                   level="DEBUG", encoding="utf-8")

# ── Pipeline ─────────────────────────────────────────────────

def run_pipeline(assignment_id: int):
    """Full pipeline for a single assignment."""
    logger.info(f"═══ Pipeline start: Assignment #{assignment_id} ═══")

    # 1. Extract
    if not extractor_agent.run(assignment_id):
        return

    # 2. Plan
    plan = planner_agent.run(assignment_id)
    if not plan:
        return

    # 3. Solve
    answers = solver_agent.run(assignment_id, plan)
    if not answers:
        return

    # 4. Verify
    confidence = verifier_agent.run(assignment_id)

    # 5. Generate documents
    docx_path, pdf_path = doc_generator_agent.run(assignment_id)
    if not pdf_path:
        return

    # 6. Upload to Drive
    drive_link = uploader_agent.run(assignment_id)
    if not drive_link:
        logger.warning("Drive upload skipped/failed — using local PDF path")
        drive_link = f"Local: {pdf_path}"
        db.update(assignment_id, drive_link=drive_link, status="drive_uploaded")

    # 7. Notify student
    notifier_agent.run(assignment_id)

    # 8. Start approval window
    approval_agent.start_approval_window(assignment_id)

    logger.info(f"═══ Pipeline complete: #{assignment_id} — awaiting approval ═══")


def check_pending_approvals():
    """Check all notified assignments for approval/timeout."""
    pending = db.get_pending()
    for record in pending:
        if record["status"] in ("notified", "approved"):
            aid = record["id"]
            result = approval_agent.process(aid)
            if result in ("approved", "auto_submitted"):
                logger.info(f"Submitting assignment #{aid}...")
                submit_assignment(aid)


def submit_assignment(assignment_id: int):
    """Submit the assignment (Playwright upload — Phase 2)."""
    record = db.get(assignment_id)
    if not record:
        return
    # Phase 1: Mark as submitted (actual Playwright upload in Phase 2)
    logger.info(f"[Phase 1] Marking #{assignment_id} as submitted (manual upload needed)")
    db.set_status(assignment_id, "submitted", "Marked submitted — Phase 2 will automate this")
    from utils.whatsapp import whatsapp
    whatsapp.send_submission_done(record.get("subject", "Assignment"))


def watcher_tick():
    """Called every interval by scheduler."""
    check_pending_approvals()
    new_ids = watcher_agent.run()
    for aid in new_ids:
        run_pipeline(aid)


# ── CLI shortcuts ─────────────────────────────────────────────

def run_once():
    """Run one watcher tick immediately — useful for testing."""
    logger.info("Running single tick...")
    watcher_tick()


def approve(assignment_id: int):
    """Manually approve an assignment from CLI."""
    approval_agent.approve_manually(assignment_id)
    console.print(f"[green]✓ Assignment #{assignment_id} approved[/green]")


def status():
    """Print current DB stats."""
    stats = db.stats()
    assignments = db.get_all(20)
    console.print(Panel(
        f"[bold]Total:[/bold] {stats['total']}  "
        f"[bold]Submitted:[/bold] {stats['submitted']}  "
        f"[bold]Pending:[/bold] {stats['pending']}",
        title="AutoAssign AI — Status"
    ))
    for a in assignments:
        console.print(
            f"  #{a['id']:3d} [{a['status']:15s}] "
            f"{a['subject'] or '?':15s}  {a['title'][:40]}"
        )


# ── Graceful shutdown ─────────────────────────────────────────

def _shutdown(sig, frame):
    logger.info("Shutting down AutoAssign AI...")
    scheduler.stop()
    sys.exit(0)


# ── Entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    # Load config
    cfg.load()
    setup_logging()

    console.print(Panel(
        "[bold green]AutoAssign AI — Starting[/bold green]\n"
        f"User: {cfg.user_name} | Interval: {cfg.check_interval}min | "
        f"Active: {cfg.active_start}–{cfg.active_end}",
        title="AutoAssign AI"
    ))

    # Handle CLI args
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "once":
            cfg.load()
            run_once()
        elif cmd == "status":
            status()
        elif cmd == "approve" and len(sys.argv) > 2:
            approve(int(sys.argv[2]))
        else:
            console.print(f"Unknown command: {cmd}")
            console.print("Usage: python3 main.py [once|status|approve <id>]")
        sys.exit(0)

    # Normal mode — start scheduler
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Run one tick immediately on start
    watcher_tick()

    # Start background scheduler
    scheduler.start(watcher_tick)

    console.print(f"[green]✓ Scheduler running — checking every {cfg.check_interval} minutes[/green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")

    while True:
        time.sleep(60)

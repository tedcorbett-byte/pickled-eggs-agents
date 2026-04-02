"""
Pickled Eggs Co — Agent Scheduler
===================================
Runs all agents on their schedules using APScheduler.
Also optionally launches the review UI after each scan.

Usage:
  python scheduler.py             # run scheduler (blocking)
  python scheduler.py --now       # run all agents once immediately, then exit
  python scheduler.py --agent listener  # run one agent immediately
  python scheduler.py --ui        # just launch the review UI

Schedules:
  Community Listener    — every 4 hours
  Content Freshness     — daily at 9:00am
  Content Multiplier    — Mondays at 8:00am
  Bar Scout             — Sundays at 10:00am (stub, not active yet)
"""
import argparse
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from agents.listener.agent import scan_reddit
from agents.content_freshness.agent import run as run_freshness
from agents.content_multiplier.agent import run as run_multiplier
from agents.bar_scout.agent import run as run_bar_scout


def run_all():
    """Run all active agents sequentially."""
    print("\n--- Community Listener ---")
    scan_reddit()
    print("\n--- Content Freshness ---")
    run_freshness()
    print("\n--- Content Multiplier ---")
    run_multiplier()


def launch_ui():
    import os
    from ui.app import app
    port = int(os.environ.get("PORT", 5050))
    print(f"\nReview Dashboard: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)


def main():
    parser = argparse.ArgumentParser(description="Pickled Eggs Co agent scheduler")
    parser.add_argument("--now",   action="store_true", help="Run all agents once and exit")
    parser.add_argument("--agent", choices=["listener", "freshness", "multiplier", "scout"],
                        help="Run a single agent immediately and exit")
    parser.add_argument("--ui",    action="store_true", help="Launch review UI only")
    args = parser.parse_args()

    if args.ui:
        launch_ui()
        return

    if args.now:
        run_all()
        return

    if args.agent:
        dispatch = {
            "listener":  scan_reddit,
            "freshness": run_freshness,
            "multiplier": run_multiplier,
            "scout":     run_bar_scout,
        }
        dispatch[args.agent]()
        return

    # ── Scheduled mode ────────────────────────────────────────────────────
    scheduler = BlockingScheduler(timezone="America/Los_Angeles")

    scheduler.add_job(
        scan_reddit,
        IntervalTrigger(hours=4),
        id="listener",
        name="Community Listener",
        max_instances=1,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        run_freshness,
        CronTrigger(hour=9, minute=0),
        id="content_freshness",
        name="Content Freshness",
        max_instances=1,
        misfire_grace_time=600,
    )

    scheduler.add_job(
        run_multiplier,
        CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="content_multiplier",
        name="Content Multiplier",
        max_instances=1,
        misfire_grace_time=600,
    )

    # Bar Scout is stubbed — uncomment when ready
    # scheduler.add_job(
    #     run_bar_scout,
    #     CronTrigger(day_of_week="sun", hour=10, minute=0),
    #     id="bar_scout",
    #     name="Bar Scout",
    # )

    print("Scheduler started. Agents will run on their schedules.")
    print("  Listener:          every 4 hours")
    print("  Content Freshness: daily at 9:00am PT")
    print("  Content Multiplier: Mondays at 8:00am PT")
    print("\nPress Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\nScheduler stopped.")


if __name__ == "__main__":
    main()

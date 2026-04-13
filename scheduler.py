"""
Pickled Eggs Co — Agent Scheduler
===================================
Runs all agents on their schedules using APScheduler.
Also optionally launches the review UI after each scan.

Usage:
  python scheduler.py             # run scheduler (blocking)
  python scheduler.py --now       # run all agents once immediately, then exit
  python scheduler.py --agent listener  # run one agent immediately (bar category)
  python scheduler.py --ui        # just launch the review UI

Schedules:
  Community Listener — daily, four categories staggered 15 min apart:
    bar:        8:00am PT
    venue:      8:15am PT
    restaurant: 8:30am PT
    rink:       8:45am PT
  Content Freshness  — daily at 9:00am PT
  Content Multiplier — Mondays at 8:00am PT
  Bar Scout — weekly Sundays, four categories staggered 30 min apart:
    bar:        10:00am PT
    venue:      10:30am PT
    restaurant: 11:00am PT
    rink:       11:30am PT
  Outreach — Wednesdays at 9:00am PT
"""
import argparse
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from shared.db import run_migrations
from agents.listener.agent import scan_reddit
from agents.content_freshness.agent import run as run_freshness
from agents.content_multiplier.agent import run as run_multiplier
from agents.bar_scout.agent import scan_for_candidates as run_bar_scout
from agents.outreach.agent import run as run_outreach


run_migrations()


def run_all():
    """Run all active agents sequentially."""
    print("\n--- Community Listener ---")
    scan_reddit()
    print("\n--- Content Freshness ---")
    run_freshness()
    print("\n--- Content Multiplier ---")
    run_multiplier()
    print("\n--- Bar Scout ---")
    run_bar_scout()
    print("\n--- Outreach ---")
    run_outreach()


def launch_ui():
    import os
    from ui.app import app
    port = int(os.environ.get("PORT", 5050))
    print(f"\nReview Dashboard: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)


def main():
    parser = argparse.ArgumentParser(description="Pickled Eggs Co agent scheduler")
    parser.add_argument("--now",   action="store_true", help="Run all agents once and exit")
    parser.add_argument("--agent", choices=["listener", "freshness", "multiplier", "scout", "outreach"],
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
            "outreach":  run_outreach,
        }
        dispatch[args.agent]()
        return

    # ── Scheduled mode ────────────────────────────────────────────────────
    scheduler = BlockingScheduler(timezone="America/Los_Angeles")

    # Community Listener — daily, four categories staggered 15 min apart
    for cat, hour, minute in [
        ("bar",        8,  0),
        ("venue",      8, 15),
        ("restaurant", 8, 30),
        ("rink",       8, 45),
    ]:
        scheduler.add_job(
            scan_reddit,
            CronTrigger(hour=hour, minute=minute),
            id=f"listener_{cat}",
            name=f"Community Listener — {cat}",
            kwargs={"category": cat},
            max_instances=1,
            misfire_grace_time=600,
        )

    # Content Freshness — daily at 9:00am PT (unchanged)
    scheduler.add_job(
        run_freshness,
        CronTrigger(hour=9, minute=0),
        id="content_freshness",
        name="Content Freshness",
        max_instances=1,
        misfire_grace_time=600,
    )

    # Content Multiplier — Mondays at 8:00am PT (unchanged)
    scheduler.add_job(
        run_multiplier,
        CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="content_multiplier",
        name="Content Multiplier",
        max_instances=1,
        misfire_grace_time=600,
    )

    # Outreach — Wednesdays at 9:00am PT
    scheduler.add_job(
        run_outreach,
        CronTrigger(day_of_week="wed", hour=9, minute=0),
        id="outreach",
        name="Outreach",
        max_instances=1,
        misfire_grace_time=600,
    )

    # Bar Scout — Sundays, four categories staggered 30 min apart
    for cat, hour, minute in [
        ("bar",        10,  0),
        ("venue",      10, 30),
        ("restaurant", 11,  0),
        ("rink",       11, 30),
    ]:
        scheduler.add_job(
            run_bar_scout,
            CronTrigger(day_of_week="sun", hour=hour, minute=minute),
            id=f"bar_scout_{cat}",
            name=f"Bar Scout — {cat}",
            kwargs={"category": cat},
            max_instances=1,
            misfire_grace_time=600,
        )

    print("Scheduler started. Registered jobs:")
    for job in scheduler.get_jobs():
        print(f"  [{job.id}] {job.name} — next run: {job.next_run_time}")
    print("\nPress Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\nScheduler stopped.")


if __name__ == "__main__":
    main()

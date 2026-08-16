"""
What's on Sydney — main orchestrator.

Usage:
  python main.py weekly    # Scrape Time Out + Urban List
  python main.py monthly   # Scrape National Parks NSW
  python main.py all       # Run both (useful for first-time setup)
"""
import argparse
import asyncio
import logging
import sys

from scrapers import scrape_timeout, scrape_urbanlist, scrape_nationalparks
from filter import filter_events
from database import EventDatabase
from site_generator import generate_site

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def run_weekly():
    """Scrape Time Out + Urban List, filter, and rebuild the website."""
    logger.info("=== WEEKLY RUN: Time Out + Urban List ===")
    db = EventDatabase()

    logger.info("Scraping Time Out Sydney...")
    timeout_events = await scrape_timeout()
    logger.info("Scraping Urban List Sydney...")
    urban_events = await scrape_urbanlist()

    raw = timeout_events + urban_events
    logger.info(f"Total raw events scraped: {len(raw)}")

    new_events = [e for e in raw if not db.is_duplicate(e.url)]
    logger.info(f"New events (not yet processed): {len(new_events)}")

    approved = await filter_events(new_events)
    logger.info(f"Events approved by AI: {len(approved)}")

    for event in approved:
        db.mark_processed(
            url=event.url,
            title=event.title,
            source=event.source,
            category=event.ai_category,
            is_free=event.is_free,
        )

    generate_site(approved)

    stats = db.stats()
    logger.info(
        f"=== Weekly run complete. New: {len(approved)}, "
        f"Total in DB: {stats['total']} ({stats['free']} free) ==="
    )


async def run_monthly():
    """Scrape National Parks NSW and rebuild the website."""
    logger.info("=== MONTHLY RUN: National Parks NSW ===")
    db = EventDatabase()

    raw = await scrape_nationalparks()
    logger.info(f"Total items scraped from NP NSW: {len(raw)}")

    new_events = [e for e in raw if not db.is_duplicate(e.url)]
    logger.info(f"New items: {len(new_events)}")

    approved = await filter_events(new_events)
    logger.info(f"Items approved: {len(approved)}")

    for event in approved:
        db.mark_processed(
            url=event.url,
            title=event.title,
            source=event.source,
            category=event.ai_category,
            is_free=event.is_free,
        )

    generate_site(approved)

    stats = db.stats()
    logger.info(f"=== Monthly run complete. New: {len(approved)}, Total: {stats['total']} ===")


async def run_all():
    await run_weekly()
    await run_monthly()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="What's on Sydney calendar bot")
    parser.add_argument(
        "mode",
        choices=["weekly", "monthly", "all"],
        help="weekly = Time Out + Urban List | monthly = National Parks | all = everything",
    )
    args = parser.parse_args()

    try:
        if args.mode == "weekly":
            asyncio.run(run_weekly())
        elif args.mode == "monthly":
            asyncio.run(run_monthly())
        else:
            asyncio.run(run_all())
    except KeyboardInterrupt:
        logger.info("Interrupted.")
        sys.exit(0)

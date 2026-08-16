"""
National Parks NSW scraper.
Scrapes walking tracks and outdoor activities for Sydney, Blue Mountains,
and Southern Highlands regions. Runs monthly (tracks don't change weekly).
"""
import asyncio
import logging
from typing import List, Optional
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout

from .base import Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.nationalparks.nsw.gov.au"

# Region slugs that map to Sydney + 2hr drive radius
TARGET_REGIONS = [
    "greater-sydney",
    "blue-mountains",
    "southern-highlands",
    "hawkesbury",
    "illawarra-shoalhaven",
    "hunter",
]

SCRAPE_URLS = [
    # Walking tracks by region
    "https://www.nationalparks.nsw.gov.au/things-to-do/walking-tracks?regions=greater-sydney&page=1",
    "https://www.nationalparks.nsw.gov.au/things-to-do/walking-tracks?regions=blue-mountains&page=1",
    "https://www.nationalparks.nsw.gov.au/things-to-do/walking-tracks?regions=southern-highlands&page=1",
    # General things to do (new facilities, pools, events)
    "https://www.nationalparks.nsw.gov.au/things-to-do?regions=greater-sydney",
    "https://www.nationalparks.nsw.gov.au/things-to-do?regions=blue-mountains",
    "https://www.nationalparks.nsw.gov.au/things-to-do?regions=southern-highlands",
    # What's on events
    "https://www.nationalparks.nsw.gov.au/whats-on?regions=greater-sydney",
    "https://www.nationalparks.nsw.gov.au/whats-on?regions=blue-mountains",
]

CARD_SELECTORS = [
    "[class*='card']",
    "article",
    "[class*='result-item']",
    "[class*='activity-item']",
    "[class*='listing-item']",
    "li[class*='item']",
]

TITLE_SELECTORS  = ["h2", "h3", "h4", "[class*='title']", "[class*='name']"]
DESC_SELECTORS   = ["[class*='description']", "[class*='summary']", "p", "[class*='intro']"]
LOC_SELECTORS    = ["[class*='location']", "[class*='park']", "[class*='region']",
                    "[class*='address']"]
DIFF_SELECTORS   = ["[class*='difficulty']", "[class*='grade']", "[class*='level']"]
DIST_SELECTORS   = ["[class*='distance']", "[class*='length']", "[class*='km']"]
DATE_SELECTORS   = ["time", "[class*='date']", "[class*='when']"]


async def _first_text(el, selectors: List[str]) -> str:
    for sel in selectors:
        try:
            child = await el.query_selector(sel)
            if child:
                text = await child.inner_text()
                if text.strip():
                    return text.strip()
        except Exception:
            continue
    return ""


async def _scrape_page(page: Page, url: str) -> List[Event]:
    events: List[Event] = []
    is_walks_page = "walking-tracks" in url

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await page.wait_for_timeout(1000)
    except PlaywrightTimeout:
        logger.warning(f"[NP NSW] Timeout: {url}")
        return events

    cards = []
    for sel in CARD_SELECTORS:
        cards = await page.query_selector_all(sel)
        if len(cards) >= 2:
            logger.debug(f"Found {len(cards)} items with '{sel}' on {url}")
            break

    if not cards:
        logger.warning(f"[NP NSW] No items found on {url}")
        return events

    for card in cards:
        try:
            title = await _first_text(card, TITLE_SELECTORS)
            if not title or len(title) < 4:
                continue

            link_el = await card.query_selector("a[href]")
            href = ""
            if link_el:
                href = await link_el.get_attribute("href") or ""
            event_url = href if href.startswith("http") else urljoin(BASE_URL, href) if href else url

            description = await _first_text(card, DESC_SELECTORS)
            location = await _first_text(card, LOC_SELECTORS)

            # For walks, enrich description with difficulty and distance
            if is_walks_page:
                difficulty = await _first_text(card, DIFF_SELECTORS)
                distance = await _first_text(card, DIST_SELECTORS)
                extras = []
                if difficulty:
                    extras.append(f"Difficulty: {difficulty}")
                if distance:
                    extras.append(f"Distance: {distance}")
                if extras:
                    description = (description + "\n" + " | ".join(extras)).strip()

            raw_date = await _first_text(card, DATE_SELECTORS)
            date_start = None
            if raw_date:
                try:
                    from dateutil import parser as dateutil_parser
                    date_start = dateutil_parser.parse(raw_date, fuzzy=True, dayfirst=True)
                except Exception:
                    pass

            # All National Parks activities are free (entry fees aside, walks are free)
            category = "outdoor"
            is_free = True

            events.append(Event(
                title=title,
                description=description,
                url=event_url,
                source="National Parks NSW",
                location=location,
                date_start=date_start,
                price_text="Free",
                is_free=is_free,
                categories=[category],
                ai_category=category,
            ))

        except Exception as e:
            logger.debug(f"[NP NSW] Skipping item: {e}")
            continue

    return events


async def scrape_nationalparks() -> List[Event]:
    """Main entry point — scrapes National Parks NSW for walks and outdoor activities."""
    all_events: List[Event] = []
    seen_urls: set = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-AU",
        )
        page = await context.new_page()

        for url in SCRAPE_URLS:
            logger.info(f"[NP NSW] Scraping {url}")
            try:
                events = await _scrape_page(page, url)
                for e in events:
                    if e.url not in seen_urls:
                        seen_urls.add(e.url)
                        all_events.append(e)
                logger.info(f"[NP NSW] Got {len(events)} items from {url}")
            except Exception as ex:
                logger.error(f"[NP NSW] Error on {url}: {ex}")
            await asyncio.sleep(2)

        await browser.close()

    logger.info(f"[NP NSW] Total unique items: {len(all_events)}")
    return all_events

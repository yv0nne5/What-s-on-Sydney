"""
Urban List Sydney scraper.
Scrapes things-to-do and events listings.
Uses Playwright because the site is JavaScript-rendered.
"""
import asyncio
import logging
import re
from datetime import datetime
from typing import List, Optional
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout

from .base import Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.theurbanlist.com"

SCRAPE_URLS = [
    "https://www.theurbanlist.com/sydney/a-list/things-to-do-in-sydney-this-weekend",
    "https://www.theurbanlist.com/sydney/a-list/free-things-to-do-in-sydney",
    "https://www.theurbanlist.com/sydney/a-list/things-to-do-in-sydney",
    "https://www.theurbanlist.com/sydney/a-list/markets-in-sydney",
    "https://www.theurbanlist.com/sydney/a-list/art-galleries-sydney",
    "https://www.theurbanlist.com/sydney/a-list/festivals-sydney",
    # Blue Mountains and surrounds
    "https://www.theurbanlist.com/sydney/a-list/things-to-do-blue-mountains",
]

CARD_SELECTORS = [
    "article",
    "[class*='card']",
    "[class*='article-item']",
    "[class*='list-item']",
    "[class*='story']",
    "li[class*='item']",
]

TITLE_SELECTORS  = ["h2", "h3", "h1", "[class*='title']", "[class*='heading']"]
DATE_SELECTORS   = ["time", "[class*='date']", "[class*='published']"]
PRICE_SELECTORS  = ["[class*='price']", "[class*='cost']", "[class*='admission']", "[class*='entry']"]
LOC_SELECTORS    = ["[class*='location']", "[class*='venue']", "[class*='suburb']", "[class*='address']"]
DESC_SELECTORS   = ["[class*='description']", "[class*='excerpt']", "[class*='intro']",
                    "[class*='standfirst']", "p"]


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
    is_free_page = "free" in url.lower()

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3500)
        # Scroll to trigger lazy loading
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(800)
    except PlaywrightTimeout:
        logger.warning(f"[Urban List] Timeout loading {url}")
        return events

    cards = []
    for sel in CARD_SELECTORS:
        cards = await page.query_selector_all(sel)
        if len(cards) >= 3:
            logger.debug(f"Found {len(cards)} cards with '{sel}' on {url}")
            break

    if not cards:
        logger.warning(f"[Urban List] No cards found on {url}")
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
            if not href:
                continue
            event_url = href if href.startswith("http") else urljoin(BASE_URL, href)

            raw_date = await _first_text(card, DATE_SELECTORS)
            date_start = _parse_date(raw_date)

            price_text = await _first_text(card, PRICE_SELECTORS)
            is_free = is_free_page or _check_free(price_text)

            location = await _first_text(card, LOC_SELECTORS)
            description = await _first_text(card, DESC_SELECTORS)

            img_el = await card.query_selector("img[src]")
            image_url: Optional[str] = None
            if img_el:
                image_url = await img_el.get_attribute("src")

            events.append(Event(
                title=title,
                description=description,
                url=event_url,
                source="Urban List Sydney",
                location=location,
                date_start=date_start,
                price_text=price_text or ("Free" if is_free else ""),
                is_free=is_free,
                image_url=image_url,
            ))

        except Exception as e:
            logger.debug(f"[Urban List] Skipping card: {e}")
            continue

    return events


def _parse_date(text: str) -> Optional[datetime]:
    if not text:
        return None
    text = re.sub(r'\b(from|until|to|–|-)\b', ' ', text, flags=re.IGNORECASE).strip()
    try:
        from dateutil import parser as dateutil_parser
        return dateutil_parser.parse(text, fuzzy=True, dayfirst=True)
    except Exception:
        return None


def _check_free(price_text: str) -> bool:
    if not price_text:
        return False
    lower = price_text.lower()
    return any(kw in lower for kw in ["free", "no charge", "$0", "complimentary", "no cost"])


async def scrape_urbanlist() -> List[Event]:
    """Main entry point — scrapes all Urban List Sydney pages."""
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
            logger.info(f"[Urban List] Scraping {url}")
            try:
                events = await _scrape_page(page, url)
                for e in events:
                    if e.url not in seen_urls:
                        seen_urls.add(e.url)
                        all_events.append(e)
                logger.info(f"[Urban List] Got {len(events)} events from {url}")
            except Exception as ex:
                logger.error(f"[Urban List] Error on {url}: {ex}")
            await asyncio.sleep(2)

        await browser.close()

    logger.info(f"[Urban List] Total unique events: {len(all_events)}")
    return all_events

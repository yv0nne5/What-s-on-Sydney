"""
Time Out Sydney scraper.
Scrapes events across festivals, art, film, markets, and free things pages.
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

BASE_URL = "https://www.timeout.com"

# Pages to scrape — covers all categories the user cares about
SCRAPE_URLS = [
    "https://www.timeout.com/sydney/things-to-do",
    "https://www.timeout.com/sydney/things-to-do/free-things-to-do-in-sydney",
    "https://www.timeout.com/sydney/art",
    "https://www.timeout.com/sydney/film",
    "https://www.timeout.com/sydney/music",
    "https://www.timeout.com/sydney/markets",
    "https://www.timeout.com/sydney/festivals",
    "https://www.timeout.com/sydney/things-to-do/best-festivals-in-sydney",
]

# Ordered lists of candidate selectors — the scraper tries each in turn
CARD_SELECTORS = [
    "article[data-testid]",
    "article",
    "[class*='card']",
    "[class*='tile']",
    "[class*='event-item']",
    "li[class*='item']",
]

TITLE_SELECTORS = ["h3", "h2", "[class*='title']", "[class*='heading']"]
DATE_SELECTORS  = ["time", "[class*='date']", "[class*='time']", "[datetime]"]
PRICE_SELECTORS = ["[class*='price']", "[class*='cost']", "[class*='admission']"]
LOC_SELECTORS   = ["[class*='location']", "[class*='venue']", "[class*='address']",
                   "[class*='neighbourhood']"]
DESC_SELECTORS  = ["[class*='description']", "[class*='standfirst']", "p", "[class*='intro']"]


async def _first_text(el, selectors: List[str]) -> str:
    """Return the text of the first matching child selector, or ''."""
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
    """Scrape a single Time Out listing page and return Event objects."""
    events: List[Event] = []
    is_free_page = "free" in url.lower()

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # Give JS time to hydrate
        await page.wait_for_timeout(3000)
        # Try scrolling to trigger lazy-load
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await page.wait_for_timeout(1500)
    except PlaywrightTimeout:
        logger.warning(f"Timeout loading {url}")
        return events

    # Find event cards
    cards = []
    for sel in CARD_SELECTORS:
        cards = await page.query_selector_all(sel)
        if len(cards) >= 3:
            logger.debug(f"Found {len(cards)} cards with selector '{sel}' on {url}")
            break

    if not cards:
        logger.warning(f"No cards found on {url}")
        return events

    for card in cards:
        try:
            # --- Title ---
            title = await _first_text(card, TITLE_SELECTORS)
            if not title:
                continue

            # --- URL ---
            link_el = await card.query_selector("a[href]")
            href = ""
            if link_el:
                href = await link_el.get_attribute("href") or ""
            if not href:
                continue
            event_url = href if href.startswith("http") else urljoin(BASE_URL, href)

            # --- Date ---
            raw_date = await _first_text(card, DATE_SELECTORS)
            date_start = _parse_date(raw_date)

            # --- Price ---
            price_text = await _first_text(card, PRICE_SELECTORS)
            is_free = is_free_page or _check_free(price_text)

            # --- Location ---
            location = await _first_text(card, LOC_SELECTORS)

            # --- Description ---
            description = await _first_text(card, DESC_SELECTORS)

            # --- Image ---
            img_el = await card.query_selector("img[src]")
            image_url: Optional[str] = None
            if img_el:
                image_url = await img_el.get_attribute("src")

            events.append(Event(
                title=title,
                description=description,
                url=event_url,
                source="Time Out Sydney",
                location=location,
                date_start=date_start,
                price_text=price_text or ("Free" if is_free else ""),
                is_free=is_free,
                image_url=image_url,
            ))

        except Exception as e:
            logger.debug(f"Skipping card due to error: {e}")
            continue

    return events


def _parse_date(text: str) -> Optional[datetime]:
    """Best-effort date parse from a raw date string."""
    if not text:
        return None
    # Remove noise words
    text = re.sub(r'\b(from|until|to|–|-)\b', ' ', text, flags=re.IGNORECASE).strip()
    try:
        from dateutil import parser as dateutil_parser
        return dateutil_parser.parse(text, fuzzy=True, dayfirst=True)
    except Exception:
        return None


def _check_free(price_text: str) -> bool:
    """Return True if price text indicates a free event."""
    if not price_text:
        return False
    lower = price_text.lower()
    return any(kw in lower for kw in ["free", "no charge", "no cost", "$0", "complimentary"])


async def scrape_timeout() -> List[Event]:
    """Main entry point — scrapes all Time Out Sydney category pages."""
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
            logger.info(f"[Time Out] Scraping {url}")
            try:
                events = await _scrape_page(page, url)
                for e in events:
                    if e.url not in seen_urls:
                        seen_urls.add(e.url)
                        all_events.append(e)
                logger.info(f"[Time Out] Got {len(events)} events from {url}")
            except Exception as e:
                logger.error(f"[Time Out] Error on {url}: {e}")
            await asyncio.sleep(2)  # polite crawl delay

        await browser.close()

    logger.info(f"[Time Out] Total unique events: {len(all_events)}")
    return all_events

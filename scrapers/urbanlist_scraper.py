"""
Urban List Sydney scraper.
Uses a JS-based extraction fallback that works regardless of CSS class names,
since Urban List uses React with obfuscated/changing class names.
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
    "https://www.theurbanlist.com/sydney/a-list/things-to-do-blue-mountains",
]

# JS snippet that extracts article links regardless of CSS class names.
# Finds <a> tags pointing to Urban List article paths and captures title + snippet.
EXTRACT_JS = """
() => {
    const seen = new Set();
    const results = [];
    document.querySelectorAll('a[href]').forEach(a => {
        const href = a.href || '';
        // Only article-style URLs (not category pages, nav, social etc.)
        if (!href.includes('/sydney/') && !href.includes('/brisbane/')
            && !href.includes('/melbourne/') && !href.includes('/perth/')) return;
        if (href.includes('/a-list/') || href.includes('/search') ||
            href.includes('instagram') || href.includes('facebook')) return;
        if (seen.has(href)) return;
        seen.add(href);

        // Walk up to find the containing block element for a description snippet
        let parent = a.parentElement;
        for (let i = 0; i < 5; i++) {
            if (!parent) break;
            const tag = (parent.tagName || '').toLowerCase();
            if (['li', 'article', 'section', 'div'].includes(tag) &&
                parent.innerText && parent.innerText.trim().length > 50) {
                break;
            }
            parent = parent.parentElement;
        }
        const blockText = parent ? parent.innerText.trim() : '';
        const title = a.innerText.trim();
        if (!title || title.length < 8 || title.length > 160) return;

        // Extract a description snippet (text around the title)
        let desc = blockText.replace(title, '').trim().substring(0, 300);

        results.push({ href, title, desc });
        if (results.length >= 35) return;
    });
    return results;
}
"""


async def _scrape_page(page: Page, url: str) -> List[Event]:
    events: List[Event] = []
    is_free_page = "free" in url.lower()
    is_blue_mountains = "blue-mountains" in url.lower()

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=35000)
        await page.wait_for_timeout(4000)
        # Scroll gradually to trigger lazy-loading
        for _ in range(4):
            await page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
            await page.wait_for_timeout(700)
    except PlaywrightTimeout:
        logger.warning(f"[Urban List] Timeout loading {url}")
        return events

    # Try classic CSS selectors first
    cards = []
    for sel in ["article", "[class*='card']", "[class*='article-item']",
                "[class*='list-item']", "[class*='story']", "li[class*='item']"]:
        cards = await page.query_selector_all(sel)
        if len(cards) >= 3:
            logger.debug(f"[Urban List] Found {len(cards)} cards with '{sel}' on {url}")
            break

    if len(cards) >= 3:
        # Classic path — parse card elements
        for card in cards:
            try:
                title = ""
                for sel in ["h2", "h3", "h1", "[class*='title']", "[class*='heading']"]:
                    el = await card.query_selector(sel)
                    if el:
                        text = await el.inner_text()
                        if text.strip():
                            title = text.strip()
                            break
                if not title or len(title) < 4:
                    continue

                link_el = await card.query_selector("a[href]")
                if not link_el:
                    continue
                href = await link_el.get_attribute("href") or ""
                if not href:
                    continue
                event_url = href if href.startswith("http") else urljoin(BASE_URL, href)

                desc = ""
                for sel in ["[class*='description']", "[class*='excerpt']",
                            "[class*='intro']", "[class*='standfirst']", "p"]:
                    el = await card.query_selector(sel)
                    if el:
                        text = await el.inner_text()
                        if text.strip():
                            desc = text.strip()
                            break

                events.append(Event(
                    title=title,
                    description=desc,
                    url=event_url,
                    source="Urban List Sydney",
                    location="Blue Mountains" if is_blue_mountains else "",
                    is_free=is_free_page,
                    price_text="Free" if is_free_page else "",
                ))
            except Exception as e:
                logger.debug(f"[Urban List] Card parse error: {e}")
                continue

    else:
        # JS fallback — extract links by URL pattern regardless of class names
        logger.info(f"[Urban List] No CSS cards found on {url} — trying JS extraction")
        try:
            items = await page.evaluate(EXTRACT_JS)
            if items:
                for item in items:
                    href = item.get("href", "")
                    title = item.get("title", "").strip()
                    desc = item.get("desc", "").strip()
                    if not href or not title or len(title) < 8:
                        continue
                    event_url = href if href.startswith("http") else urljoin(BASE_URL, href)
                    events.append(Event(
                        title=title,
                        description=desc,
                        url=event_url,
                        source="Urban List Sydney",
                        location="Blue Mountains" if is_blue_mountains else "",
                        is_free=is_free_page,
                        price_text="Free" if is_free_page else "",
                    ))
                logger.info(f"[Urban List] JS extraction found {len(events)} items on {url}")
            else:
                logger.warning(f"[Urban List] JS extraction also found nothing on {url}")
        except Exception as e:
            logger.error(f"[Urban List] JS extraction error on {url}: {e}")

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
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-AU",
            viewport={"width": 1280, "height": 900},
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

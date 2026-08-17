"""
Site generator — produces index.html in neo-brutalism style.
Colour scheme: bubblegum pink + yellow (Gumroad-inspired).
Each event card has a one-click "Add to Google Calendar" button.
Hosted for free via GitHub Pages.
"""
import html as html_lib
import os
from datetime import datetime
from typing import List
from urllib.parse import quote

from scrapers.base import Event

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "index.html")

# Pink = #FF90E8  |  Yellow = #FFE500  |  Black = #0a0a0a
PINK   = "#FF90E8"
YELLOW = "#FFE500"
BLACK  = "#0a0a0a"

CATEGORY_META = {
    "festival":  {"label": "Festival",  "css": "hdr-festival"},
    "market":    {"label": "Market",    "css": "hdr-market"},
    "art":       {"label": "Art",       "css": "hdr-art"},
    "outdoor":   {"label": "Outdoor",   "css": "hdr-outdoor"},
    "food":      {"label": "Food",      "css": "hdr-food"},
    "community": {"label": "Community", "css": "hdr-community"},
    "other":     {"label": "Event",     "css": "hdr-other"},
}

REGION_LABELS = {
    "sydney":             "Sydney",
    "blue_mountains":     "Blue Mountains",
    "southern_highlands": "Southern Highlands",
    "hunter_valley":      "Hunter Valley",
    "illawarra":          "Illawarra",
}


def generate_site(events: List[Event], output_path: str = OUTPUT_FILE) -> None:
    """Generate index.html from a list of approved events."""
    now = datetime.now().strftime("%d %b %Y").lstrip("0")
    cards_html = "\n".join(_card_html(e) for e in events)
    page = _build_page(cards_html, len(events), now)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"[Site] Generated {output_path} with {len(events)} events")


# ── helpers ──────────────────────────────────────────────────────────────────

def _gcal_url(event: Event) -> str:
    """Build a pre-filled Google Calendar 'add event' URL."""
    params: dict = {"action": "TEMPLATE", "text": event.title}

    if event.date_start:
        has_time = bool(event.date_start.hour or event.date_start.minute)
        fmt = "%Y%m%dT%H%M%S" if has_time else "%Y%m%d"
        start_str = event.date_start.strftime(fmt)
        end_str = (event.date_end or event.date_start).strftime(fmt)
        params["dates"] = f"{start_str}/{end_str}"

    details_parts = []
    if event.description:
        details_parts.append(event.description[:300])
    if event.price_text:
        details_parts.append(f"Price: {event.price_text}")
    details_parts.append(f"More info: {event.url}")
    params["details"] = "\n".join(details_parts)

    if event.location:
        params["location"] = event.location

    qs = "&".join(f"{k}={quote(str(v), safe='')}" for k, v in params.items())
    return f"https://calendar.google.com/calendar/render?{qs}"


def _fmt_date(event: Event) -> str:
    if not event.date_start:
        return "Date TBC"
    start = event.date_start.strftime("%d %b").lstrip("0")
    if event.date_end and event.date_end.date() != event.date_start.date():
        end = event.date_end.strftime("%d %b %Y").lstrip("0")
        return f"{start} – {end}"
    return event.date_start.strftime("%d %b %Y").lstrip("0")


def _card_html(event: Event) -> str:
    cat = event.ai_category or "other"
    meta = CATEGORY_META.get(cat, CATEGORY_META["other"])
    region_label = REGION_LABELS.get(event.ai_location_region, "Sydney")

    badge = (
        '<span class="badge badge-free">Free</span>'
        if event.is_free
        else f'<span class="badge badge-paid">{html_lib.escape(event.price_text or "Paid")}</span>'
    )

    desc = html_lib.escape((event.description or "")[:220])
    title = html_lib.escape(event.title)
    location = html_lib.escape(event.location or "Sydney area")
    gcal = html_lib.escape(_gcal_url(event))

    return f"""    <div class="card" data-cat="{cat}" data-region="{event.ai_location_region or 'sydney'}" data-free="{'true' if event.is_free else 'false'}">
      <div class="card-hdr {meta['css']}">
        <span class="card-cat-label">{meta['label']}</span>
        {badge}
      </div>
      <div class="card-body">
        <p class="card-title">{title}</p>
        <div class="card-meta">
          <span class="meta-item">📅 {_fmt_date(event)}</span>
          <span class="meta-item">📍 {location}</span>
        </div>
        <p class="card-desc">{desc}</p>
      </div>
      <div class="card-foot">
        <div class="tags">
          <span class="tag">{meta['label']}</span>
          <span class="tag">{region_label}</span>
        </div>
        <a href="{gcal}" target="_blank" rel="noopener" class="add-btn">+ Add to calendar</a>
      </div>
    </div>"""


# ── full page template ────────────────────────────────────────────────────────

def _build_page(cards_html: str, count: int, updated: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>What's on Sydney</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: {PINK};
      color: {BLACK};
      min-height: 100vh;
    }}

    /* ── HERO ── */
    .hero {{
      background: {BLACK};
      padding: 2rem 1.5rem 1.5rem;
      border-bottom: 3px solid {BLACK};
    }}
    .hero-eyebrow {{
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: {PINK};
      margin-bottom: 10px;
    }}
    .hero-title {{
      font-size: 36px;
      font-weight: 700;
      color: #fff;
      line-height: 1.1;
    }}
    .hero-title span {{ color: {YELLOW}; }}
    .hero-sub {{
      font-size: 13px;
      color: rgba(255,255,255,0.5);
      margin-top: 10px;
      letter-spacing: 0.03em;
    }}
    #live-count {{ color: {YELLOW}; font-weight: 700; }}

    /* ── FILTERS ── */
    .filters {{
      background: #fff;
      border-bottom: 3px solid {BLACK};
      padding: 1rem 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 10px;
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    .filter-row {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      align-items: center;
    }}
    .flabel {{
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: #999;
      min-width: 52px;
    }}
    .pill {{
      font-size: 12px;
      font-weight: 600;
      padding: 5px 14px;
      border: 2px solid {BLACK};
      background: #fff;
      color: {BLACK};
      cursor: pointer;
      border-radius: 999px;
      box-shadow: 2px 2px 0 {BLACK};
      transition: transform 0.08s, box-shadow 0.08s;
      user-select: none;
    }}
    .pill:hover {{ transform: translate(1px, 1px); box-shadow: 1px 1px 0 {BLACK}; }}
    .pill.active {{ background: {BLACK}; color: {YELLOW}; }}
    .pill[data-value="free"].active      {{ background: {YELLOW}; color: {BLACK}; border-color: {BLACK}; }}
    .pill[data-value="festival"].active  {{ background: #FF4D6D; color: #fff; border-color: #FF4D6D; box-shadow: 2px 2px 0 {BLACK}; }}
    .pill[data-value="market"].active    {{ background: #FF9F1C; color: {BLACK}; border-color: #FF9F1C; box-shadow: 2px 2px 0 {BLACK}; }}
    .pill[data-value="art"].active       {{ background: #7B2FBE; color: #fff; border-color: #7B2FBE; box-shadow: 2px 2px 0 {BLACK}; }}
    .pill[data-value="outdoor"].active   {{ background: #2DC653; color: #fff; border-color: #2DC653; box-shadow: 2px 2px 0 {BLACK}; }}
    .pill[data-value="community"].active {{ background: {PINK}; color: {BLACK}; border-color: {BLACK}; box-shadow: 2px 2px 0 {BLACK}; }}

    /* ── CARDS ── */
    .cards {{
      padding: 1.5rem;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 18px;
      background: {PINK};
    }}
    .card {{
      background: #fff;
      border: 3px solid {BLACK};
      border-radius: 16px;
      box-shadow: 5px 5px 0 {BLACK};
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .card[hidden] {{ display: none !important; }}

    /* card header colours */
    .card-hdr {{
      padding: 0.6rem 1rem;
      border-bottom: 3px solid {BLACK};
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }}
    .hdr-festival  {{ background: #FF4D6D; }}
    .hdr-market    {{ background: #FF9F1C; }}
    .hdr-art       {{ background: #7B2FBE; }}
    .hdr-outdoor   {{ background: #2DC653; }}
    .hdr-food      {{ background: #FF6B35; }}
    .hdr-community {{ background: {PINK}; }}
    .hdr-other     {{ background: #aaa; }}

    .card-cat-label {{
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: {BLACK};
    }}
    .hdr-art .card-cat-label,
    .hdr-other .card-cat-label {{ color: #fff; }}

    .badge {{
      font-size: 11px;
      font-weight: 700;
      padding: 3px 10px;
      border: 2px solid {BLACK};
      border-radius: 999px;
    }}
    .badge-free {{ background: {YELLOW}; color: {BLACK}; }}
    .badge-paid {{ background: #fff;     color: {BLACK}; }}

    .card-body {{
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 8px;
      flex: 1;
    }}
    .card-title {{
      font-size: 15px;
      font-weight: 700;
      line-height: 1.4;
      color: {BLACK};
    }}
    .card-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .meta-item {{
      font-size: 12px;
      color: #555;
    }}
    .card-desc {{
      font-size: 13px;
      color: #444;
      line-height: 1.65;
      border-left: 3px solid {PINK};
      padding-left: 10px;
      flex: 1;
    }}

    .card-foot {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
      padding: 0.75rem 1rem;
      border-top: 3px solid {BLACK};
      background: {YELLOW};
    }}
    .tags {{ display: flex; gap: 5px; flex-wrap: wrap; }}
    .tag {{
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      padding: 3px 10px;
      border: 2px solid {BLACK};
      border-radius: 999px;
      background: #fff;
      color: {BLACK};
    }}

    .add-btn {{
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      padding: 7px 16px;
      border: 2px solid {BLACK};
      border-radius: 999px;
      background: {PINK};
      color: {BLACK};
      cursor: pointer;
      box-shadow: 3px 3px 0 {BLACK};
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: transform 0.08s, box-shadow 0.08s;
      white-space: nowrap;
    }}
    .add-btn:hover {{ transform: translate(2px, 2px); box-shadow: 1px 1px 0 {BLACK}; }}

    /* ── EMPTY STATE ── */
    .empty {{
      display: none;
      grid-column: 1 / -1;
      text-align: center;
      padding: 3rem 1rem;
      border: 3px dashed {BLACK};
      border-radius: 16px;
      font-size: 15px;
      font-weight: 600;
      color: {BLACK};
      background: #fff;
    }}

    /* ── FOOTER ── */
    .footer {{
      text-align: center;
      padding: 1.5rem;
      font-size: 12px;
      border-top: 3px solid {BLACK};
      background: {BLACK};
      color: rgba(255,255,255,0.4);
    }}
    .footer a {{ color: {YELLOW}; text-decoration: none; }}

    @media (max-width: 500px) {{
      .hero-title {{ font-size: 28px; }}
      .cards {{ padding: 1rem; gap: 14px; }}
    }}
  </style>
</head>
<body>

<header class="hero">
  <p class="hero-eyebrow">Sydney &amp; surrounds · Auto-updated weekly</p>
  <h1 class="hero-title">What's on <span>Sydney</span></h1>
  <p class="hero-sub"><span id="live-count">{count}</span> things to do · Updated {updated}</p>
</header>

<div class="filters">
  <div class="filter-row">
    <span class="flabel">Vibe</span>
    <button class="pill active" data-filter="cat" data-value="all">All</button>
    <button class="pill" data-filter="cat" data-value="free">Free only</button>
    <button class="pill" data-filter="cat" data-value="festival">Festivals</button>
    <button class="pill" data-filter="cat" data-value="market">Markets</button>
    <button class="pill" data-filter="cat" data-value="art">Art</button>
    <button class="pill" data-filter="cat" data-value="outdoor">Outdoor</button>
    <button class="pill" data-filter="cat" data-value="community">Community</button>
  </div>
  <div class="filter-row">
    <span class="flabel">Where</span>
    <button class="pill active" data-filter="region" data-value="all">Everywhere</button>
    <button class="pill" data-filter="region" data-value="sydney">Sydney</button>
    <button class="pill" data-filter="region" data-value="blue_mountains">Blue Mountains</button>
    <button class="pill" data-filter="region" data-value="southern_highlands">S. Highlands</button>
    <button class="pill" data-filter="region" data-value="hunter_valley">Hunter Valley</button>
    <button class="pill" data-filter="region" data-value="illawarra">Illawarra</button>
  </div>
</div>

<main class="cards" id="cards">
{cards_html}
  <p class="empty" id="empty-msg">No events match these filters — try broadening your search. 🌸</p>
</main>

<footer class="footer">
  What's on Sydney · Auto-updated every Monday via GitHub Actions ·
  <a href="https://www.timeout.com/sydney" target="_blank">Time Out</a> ·
  <a href="https://www.theurbanlist.com/sydney" target="_blank">Urban List</a> ·
  <a href="https://www.nationalparks.nsw.gov.au" target="_blank">National Parks NSW</a>
</footer>

<script>
  const cards = Array.from(document.querySelectorAll('.card'));
  const emptyMsg = document.getElementById('empty-msg');
  const liveCount = document.getElementById('live-count');

  let activeCat = 'all';
  let activeRegion = 'all';

  function applyFilters() {{
    let visible = 0;
    cards.forEach(card => {{
      const cat = card.dataset.cat;
      const region = card.dataset.region;
      const free = card.dataset.free === 'true';

      const matchCat = activeCat === 'all' || activeCat === 'free'
        ? (activeCat === 'free' ? free : true)
        : cat === activeCat;
      const matchRegion = activeRegion === 'all' || region === activeRegion;

      if (matchCat && matchRegion) {{
        card.hidden = false;
        visible++;
      }} else {{
        card.hidden = true;
      }}
    }});

    liveCount.textContent = visible;
    emptyMsg.style.display = visible === 0 ? 'block' : 'none';
  }}

  document.querySelectorAll('.pill').forEach(pill => {{
    pill.addEventListener('click', () => {{
      const filter = pill.dataset.filter;
      const value = pill.dataset.value;

      document.querySelectorAll(`.pill[data-filter="${{filter}}"]`).forEach(p => p.classList.remove('active'));
      pill.classList.add('active');

      if (filter === 'cat') activeCat = value;
      if (filter === 'region') activeRegion = value;

      applyFilters();
    }});
  }});
</script>
</body>
</html>"""

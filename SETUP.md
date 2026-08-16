# What's on Sydney — Setup Guide

This guide takes ~30 minutes. You'll need a Google account, a Claude API key, and a GitHub account.

---

## Step 1 — Create the Google Calendar

1. Go to [Google Calendar](https://calendar.google.com)
2. In the left sidebar, click **+** next to "Other calendars" → **Create new calendar**
3. Name it **What's on Sydney**, add a description if you like, click **Create calendar**
4. To share with friends: click the three dots next to the calendar → **Settings** → **Share with specific people** → add their email addresses

---

## Step 2 — Set up Google Cloud (for API access)

> This lets the bot write events to your calendar automatically.

### 2a. Create a project
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click the project dropdown (top left) → **New Project** → name it `sydnet-activities` → **Create**

### 2b. Enable the Calendar API
1. In your new project, go to **APIs & Services → Library**
2. Search for **Google Calendar API** → click it → **Enable**

### 2c. Create a Service Account
1. Go to **APIs & Services → Credentials**
2. Click **+ Create Credentials → Service Account**
3. Name: `sydnet-bot` → click **Create and Continue** → **Done**
4. Click on the service account you just created → **Keys** tab → **Add Key → Create new key → JSON**
5. A JSON file downloads — keep it safe (you'll use it in Step 4)

### 2d. Note the service account email
On the service account page, copy the email address (looks like `sydnet-bot@your-project.iam.gserviceaccount.com`)

---

## Step 3 — Share your calendar with the service account

1. Back in Google Calendar, click the three dots next to **What's on Sydney** → **Settings**
2. Scroll to **Share with specific people** → **Add people**
3. Paste the service account email from Step 2d
4. Set permission to **Make changes to events** → **Send**

### Find your Calendar ID
1. Still in calendar settings, scroll to **Integrate calendar**
2. Copy the **Calendar ID** (looks like `abc123@group.calendar.google.com`) — you'll need it in Step 4

---

## Step 4 — Get a Claude API key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up or log in
3. Go to **API Keys** → **Create Key** → copy the key

> The bot uses Claude Haiku (cheapest model) for event filtering. Estimated cost: ~$0.50–$2 per month depending on how many events are scraped.

---

## Step 5 — Create a GitHub repository

1. Go to [github.com](https://github.com) → **New repository**
2. Name it `sydnet-activities`, set it to **Private** (recommended), click **Create**
3. Upload all files from the `2026-07-19-sydnet-activities/` folder to the repo root
   - You can drag-and-drop in the GitHub web UI, or use `git push`

### Add GitHub Secrets (so keys never appear in your code)
1. In your repo, go to **Settings → Secrets and variables → Actions**
2. Click **New repository secret** and add these three:

| Secret name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Claude API key from Step 4 |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | The **entire contents** of the JSON file from Step 2c |
| `GOOGLE_CALENDAR_ID` | The Calendar ID from Step 3 |

---

## Step 6 — First run (manual test)

Before the automatic schedule kicks in, run it manually to confirm everything works:

1. In your GitHub repo, go to **Actions**
2. Click **Weekly Scrape — Time Out + Urban List** in the left list
3. Click **Run workflow → Run workflow**
4. Watch the logs — look for lines like `[Calendar] Added: 🟢 ...`
5. Check your Google Calendar — events should appear within a minute

Repeat for the **Monthly Scrape** workflow if you want to test National Parks too.

---

## Step 7 — Automatic schedule

Once the manual run succeeds, the workflows will run automatically:

- **Weekly** — every Monday night (events appear Tuesday morning Sydney time)
- **Monthly** — 1st of each month (new walks/outdoor listings)

You can also trigger either workflow manually at any time from the **Actions** tab.

---

## Colour legend in your calendar

| Colour | Meaning |
|---|---|
| 🟢 Green (Sage) | Free event |
| 🌿 Orange (Tangerine) | Outdoor / walk / nature |
| 💰 Yellow (Banana) | Paid event |

---

## Troubleshooting

**"No cards found" in logs** — The website's HTML structure changed. Open an issue or check if the site has a new layout; selectors in `scrapers/timeout_scraper.py` and `scrapers/urbanlist_scraper.py` may need updating.

**"GOOGLE_SERVICE_ACCOUNT_JSON is not set"** — Check the secret is saved correctly in GitHub Settings → Secrets. Make sure the entire JSON content is pasted (including the outer `{ }`).

**Events added with wrong date** — The date scraping is best-effort. You can manually edit these in Google Calendar. Date parsing will improve as the sites are observed over time.

**Rate limit from Claude API** — If you see 429 errors, the batch size in `filter.py` can be reduced (change `batch_size=15` to `batch_size=8`).

---

## Subscribing friends to the calendar

1. In Google Calendar → **What's on Sydney** → three dots → **Settings**
2. Under **Integrate calendar**, copy the **Public URL to this calendar** (`.ics` link)
3. Share that link — friends can add it to Google Calendar, Apple Calendar, or Outlook
4. Or: use **Share with specific people** to give them a managed invite

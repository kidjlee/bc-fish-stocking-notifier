# 🎣 BC Fish Stocking Notifier

[![Daily Fish Stocking Check](https://github.com/kidjlee/bc-fish-stocking-notifier/actions/workflows/daily_check.yml/badge.svg)](https://github.com/kidjlee/bc-fish-stocking-notifier/actions/workflows/daily_check.yml)

A zero-cost, zero-server bot that watches the [GoFishBC stocking report](https://www.gofishbc.com/stocked-fish/)
for the **Lower Mainland (Region 2)** and sends you a **Telegram** message
whenever new lakes get stocked with fish.

It runs entirely on **GitHub Actions** — there is **no computer to keep on** and
**no database to manage**. GitHub's cloud servers run the check on a daily cron
schedule and commit the tracking state back to this repo.

---

## What the bot does

Every day at **7:00 AM Pacific**, the bot:

1. Fetches the GoFishBC stocking report filtered to the Lower Mainland.
2. Parses every stocking event (waterbody, species, strain, count, date).
3. Compares them against `data/seen_events.json` (lightweight persistent storage).
4. If there are **new** stocking events, sends you a Telegram message like:

   ```
   🎣 New fish stocked in the Lower Mainland!

   📍 Lafarge
      Species: Rainbow Trout (Fraser Valley Triploid)
      Count: 500 fish
      Date: June 14, 2026

   📍 Buntzen
      Species: Rainbow Trout
      Count: 300 fish
      Date: June 14, 2026

   Check details: https://www.gofishbc.com/stocked-fish/
   ```

5. Commits the updated `data/seen_events.json` back to the repo so the same
   events aren't reported twice.

If nothing new was stocked, the bot **sends nothing** (a silent run).

> **Note on the first run:** the report contains hundreds of historical events.
> The very first run (when `seen_events.json` is empty) simply records everything
> as "already seen" and sends **no** notification. From then on you'll only be
> pinged about genuinely new stockings.

---

## How it works (no local computer needed)

```
GitHub Actions (cron)  ──►  main.py
                              ├─ scraper.py   → GET gofishbc.com (Region 2 HTML table)
                              ├─ compare with data/seen_events.json
                              └─ notifier.py  → Telegram Bot API → your phone
                            commit updated seen_events.json back to repo
```

The stocking report is served as plain server-rendered HTML (the data is in the
page table when you pass `?region=LOWER MAINLAND`), so no headless browser is
required — just `requests` + `BeautifulSoup`.

---

## One-time setup

### a. Create a Telegram bot and get the token

1. Open Telegram and message [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts (give it a name and username).
3. BotFather replies with a **token** that looks like
   `123456789:ABCdefGhIJKlmNoPQRsTUVwxyz`. Copy it.

### b. Get your Telegram chat ID

1. Message [@userinfobot](https://t.me/userinfobot) on Telegram.
2. It replies with your numeric **chat ID** (e.g. `12345678`). Copy it.
3. **Important:** open a chat with *your* new bot and send it any message (e.g.
   `hi`). A bot cannot message you until you've messaged it first.

### c. Add both as GitHub Secrets

In this repository on GitHub:

1. Go to **Settings → Secrets and variables → Actions → New repository secret**.
2. Add a secret named `TELEGRAM_BOT_TOKEN` with the token from step (a).
3. Add a secret named `TELEGRAM_CHAT_ID` with the chat ID from step (b).

### d. Enable GitHub Actions

1. Go to the **Actions** tab of the repo.
2. If prompted, click **"I understand my workflows, enable them"**.
3. The **Daily Fish Stocking Check** workflow will now run on schedule.

> The workflow needs permission to push the updated state file. This repo's
> workflow already requests `permissions: contents: write`. If pushes fail,
> check **Settings → Actions → General → Workflow permissions** and ensure
> **"Read and write permissions"** is selected.

---

## Trigger a manual test run

You don't have to wait until 7 AM to test it:

1. Go to the **Actions** tab.
2. Select **Daily Fish Stocking Check** in the left sidebar.
3. Click **Run workflow → Run workflow**.

The first manual run just seeds the state file (no notification). To force a test
notification, run it once to seed, then remove a few IDs from
`data/seen_events.json`, commit, and run it again — those events will be reported
as "new".

---

## Run locally (optional)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # then fill in your token + chat id
python main.py
```

`scraper.py` can also be run directly to preview the parsed data:

```bash
python scraper.py
```

---

## Seasonality

BC's stocking season runs roughly **March through October**. Expect frequent
notifications in spring and summer, and a **quiet bot over the winter** — that's
normal, not a bug.

---

## Project layout

```
bc-fish-stocking-notifier/
├── .github/workflows/daily_check.yml   # GitHub Actions cron workflow
├── data/seen_events.json               # tracks previously seen events
├── scraper.py                          # fetches + parses GoFishBC data
├── notifier.py                         # sends the Telegram message
├── main.py                             # orchestrates a full run
├── requirements.txt                    # Python dependencies
├── .env.example                        # documents required secrets
└── README.md
```

## Required secrets

| Secret | Where to get it |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) on Telegram |
| `TELEGRAM_CHAT_ID` | [@userinfobot](https://t.me/userinfobot) on Telegram |

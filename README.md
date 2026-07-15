# pa.liftingdatabase.com → NeonDB

Scrapes powerlifting competition results from <https://pa.liftingdatabase.com/>
and loads them into a NeonDB (Postgres) database.

The pipeline is **scrape → raw-cache → parse → load**: every fetched page is
cached under `raw_html/`, so re-parsing and re-loading cost no network, and the
crawl is safe to stop and resume at any time.

## What gets collected

| Table          | Contents |
|----------------|----------|
| `competitions` | ~553 meets: name, date, sanction #, state, meet director |
| `results`      | One row per lifter entry per event: division, sex, equipment, weight class, bodyweight, placing, total, points |
| `attempts`     | Every individual attempt (up to 9 per entry): squat/bench/deadlift, attempt 1–3, weight in kg, make/miss, video id |
| `lifters`      | Lifter profiles: name, birth year, state |
| `teams`        | Clubs referenced by results |
| `records`      | State + national records, imported from the site's CSV export |

All weights are stored in **kilograms** (the site's canonical unit).

## Setup

```bash
cd POWERLIFTING
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
# paste your Neon connection string into .env as DATABASE_URL=...
```

Get the connection string from the Neon dashboard → your project →
**Connection Details** → *Connection string* (it ends with `?sslmode=require`).

## Usage

```bash
.venv/bin/python run.py init-db                      # create tables
.venv/bin/python run.py scrape-competitions --limit 2  # smoke test: 2 meets
.venv/bin/python run.py stats                        # row counts

# full crawl (competitions, lifter detail, teams, records)
.venv/bin/python run.py all
```

Individual stages:

```bash
.venv/bin/python run.py scrape-competitions   # all meets + results + attempts
.venv/bin/python run.py scrape-lifters         # fill in lifter birth year / state
.venv/bin/python run.py scrape-teams           # team names
.venv/bin/python run.py scrape-records         # records CSV import
```

Flags:
- `--limit N` — process only the first N items (smoke testing)
- `--refetch` — bypass the `raw_html/` cache and re-download
- `--force` — re-load competitions into the DB even if already present

Re-running is idempotent: competitions are upserted and their results replaced,
so nothing duplicates.

## Using it for a different federation

Any federation hosted on the same `liftingdatabase.com` platform works with no code
changes — the page structure is identical. Point the scraper at the other subdomain
by setting `BASE_URL` in `.env`:

```bash
BASE_URL=https://XX.liftingdatabase.com
```

Use a separate NeonDB database (a different `DATABASE_URL`) per federation so their
data stays isolated. The `raw_html/` cache is keyed by page, so give each federation
its own checkout (or clear `raw_html/`) to avoid mixing cached pages.

## Politeness

Requests are rate-limited (default 1/sec, set `SCRAPE_DELAY_SECONDS` in `.env`)
with exponential-backoff retries. The raw HTML cache means a second run touches
the site only for pages it hasn't seen.

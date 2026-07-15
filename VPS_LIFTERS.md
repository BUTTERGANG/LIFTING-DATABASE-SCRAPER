# Running the lifter-detail stage on a VPS

> **Optional.** The competition results tables already include each lifter's
> **year of birth** and **home state**, and the initial load populated both for
> all lifters. So this stage is not needed to complete those fields. Its only
> remaining value is re-confirming that data and (optionally) per-lifter
> personal-best history, which is already derivable from the loaded results.
> Documented here in case you want it anyway on the Powerlifting America data,
> and as the pattern to reuse for another federation.

The **lifter-detail** stage is the long one (~10k+ pages at 1 req/sec ≈ 3–4 h),
so it's split out to run on a VPS against the **same NeonDB**.

What it does: for every lifter whose `birth_year` is still NULL, it fetches
`lifters-view?id=N` and fills in **birth year** and **home state**. Everything
else about each lifter (name, their results, and all attempts) is already loaded.
Note: after the standard full load there are usually **no** such lifters left,
so this will report 0 to do unless you're running it against a fresh DB where
the competition stage did not capture YOB.

It is **resumable and idempotent** — safe to stop/restart; it only re-fetches
lifters still missing detail.

## Setup on the VPS

```bash
git clone https://github.com/BUTTERGANG/LIFTING-DATABASE-SCRAPER.git
cd LIFTING-DATABASE-SCRAPER
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
# Edit .env and set BOTH to the SAME values used for the main load:
#   DATABASE_URL=<the same Neon connection string>
#   BASE_URL=https://pa.liftingdatabase.com
```

## Run it (detached, survives SSH disconnect)

```bash
nohup .venv/bin/python run.py scrape-lifters > lifters.log 2>&1 &

# watch progress
tail -f lifters.log

# how many remain (birth_year still NULL)
.venv/bin/python -c "import db;c=db.connect().cursor();c.execute(\"SELECT count(*) FROM lifters WHERE birth_year IS NULL\");print(c.fetchone()[0],'remaining')"
```

## Notes

- Point it at the **same** `DATABASE_URL` as the main load so it updates the
  existing lifter rows in place — do **not** use a fresh database.
- The VPS builds its own `raw_html/` cache; it does not need this machine's cache.
- Optional speed-up: raise the crawl rate by setting `SCRAPE_DELAY_SECONDS=0.4`
  in `.env` (≈2.5 req/sec, ~1.5 h) — a bit harder on the source site.
- When finished, all lifters will have birth year + state where the site
  publishes them (some pages legitimately omit one or both).

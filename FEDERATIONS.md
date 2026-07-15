# Federations on the liftingdatabase.com platform

`liftingdatabase.com` is a hosted platform; each federation gets its own
subdomain running the **identical** page structure. This scraper works against
any of them unchanged — just set `BASE_URL` in `.env` and point at a fresh
database.

## Confirmed federation instances

| Subdomain | Federation | Competitions | Status |
|---|---|---|---|
| `pa.liftingdatabase.com` | Powerlifting America | 553 | ✅ Loaded (see `CHANGELOG.md`) |
| `usapl.liftingdatabase.com` | USA Powerlifting | ~4,731 | Not loaded (~8.5× the size of PA) |

Both were verified to use the same `competition_view_results` table and the same
`lift_{lifter}_{slot}_{discipline}_{entry}` attempt-cell scheme, so the parser
and loader need no changes between them.

## Not federation data (excluded)

- `usapltest.liftingdatabase.com` — a **staging/test mirror** of usapl (page
  title says "TEST", ~4,643 comps, same data slightly behind). Do not load.
- `www.liftingdatabase.com` / root `liftingdatabase.com` — the platform vendor's
  marketing site, not federation data.
- `mail.liftingdatabase.com` — mail server infrastructure.

## Discovery method & caveat

Instances were found via certificate transparency (certspotter) and passive DNS
(HackerTarget), then confirmed by fetching `/competitions` and checking the page
structure. A wildcard-DNS check was negative, so resolved subdomains are real.

**Caveat:** the platform sits behind Cloudflare. CT logs and passive DNS only
reveal subdomains that were publicly observed, so an instance that never got its
own logged certificate could exist without appearing here. Common federation
acronyms (uspa, ipf, epf, wrpf, rps, spf, apf, etc.) were probed directly and
did **not** resolve. If you know a specific federation on this platform, check
its exact subdomain directly.

## Loading another federation

```bash
git clone https://github.com/BUTTERGANG/LIFTING-DATABASE-SCRAPER.git
cd LIFTING-DATABASE-SCRAPER
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env
# In .env:
#   BASE_URL=https://usapl.liftingdatabase.com
#   DATABASE_URL=<a fresh NeonDB, separate per federation>
.venv/bin/python run.py init-db
./run_all.sh          # competitions -> teams -> records (lifter stage optional)
```

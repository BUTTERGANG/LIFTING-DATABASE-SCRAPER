# Changelog

## Initial full load of pa.liftingdatabase.com (2026-07-15)

First complete scrape of the Powerlifting America instance into NeonDB.

### Final dataset

| Table          | Rows     |
|----------------|----------|
| competitions   | 553      |
| results        | 22,285   |
| attempts       | 200,565  |
| lifters        | 9,702    |
| teams          | 487      |
| records        | 97,381   |

Meets span **2020-01-01 → 2026-06-27**. All weights in kilograms.

Integrity verified after load: 0 orphan results, 0 orphan attempts, max 9
attempts per result, every competition has a date, and all 9,702 lifters have
birth year and state.

### Fixes made during the real run

Building against live data surfaced four issues, each fixed and reflected in the
schema/loader:

1. **`placing` is a Postgres reserved word.** The results column is `placement`
   (the parser dict still uses the key `placing`).
2. **`id=0` is a "no team / no lifter" placeholder** on the site.
   `parse._href_id` now maps any id ≤ 0 to NULL, avoiding FK violations on
   `results.team_id`.
3. **A lifter can appear twice in one division** (double registration) with
   distinct `entry_id`s. The results natural key is therefore
   `(competition_id, entry_id)`, not `(competition_id, lifter_id, event,
   division, weight_class)`.
4. **Slow loading from per-row INSERTs.** The loader now batches with
   `execute_values` (results + attempts + referenced lifters/teams), cutting
   DB round-trips per meet from hundreds to ~4 (~7× faster on the DB-bound
   portion).

### Note on lifter detail

The competition results tables already include each lifter's **year of birth**
and **home state**, so those fields are fully populated without visiting
individual lifter pages. The separate `scrape-lifters` stage (see
`VPS_LIFTERS.md`) is therefore **optional** — it only re-confirms those fields
and could add per-lifter personal-best history, which is already derivable from
the loaded results. It was skipped in this run.

### Operational tooling added

- `run_all.sh` — autonomous, detached, `caffeinate`-wrapped chain of all stages,
  with per-stage retry. Resumable and idempotent.
- `VPS_LIFTERS.md` — runbook for the optional lifter-detail crawl on a VPS
  against the same NeonDB.

#!/usr/bin/env python3
"""CLI orchestrator for scraping pa.liftingdatabase.com into NeonDB.

Usage:
    python run.py init-db
    python run.py scrape-competitions [--limit N] [--force] [--refetch]
    python run.py scrape-lifters      [--limit N] [--refetch]
    python run.py scrape-teams        [--limit N] [--refetch]
    python run.py scrape-records      [--refetch]
    python run.py all                 [--limit N]
    python run.py stats

--force    : re-load into DB even if already present (competitions)
--refetch  : bypass the raw_html cache and re-download from the site
--limit N  : only process the first N items (handy for a smoke test)
"""
from __future__ import annotations

import sys
import argparse

import fetch
import parse
import records as records_mod
import db


def _log(msg: str):
    print(msg, flush=True)


def cmd_init_db(args):
    conn = db.connect()
    db.init_db(conn)
    conn.close()
    _log("Schema created/verified.")


def cmd_scrape_competitions(args):
    conn = db.connect()
    cur = conn.cursor()
    html = fetch.competition_list(force=args.refetch)
    comps = parse.parse_competition_list(html)
    _log(f"Found {len(comps)} competitions in the list.")

    already = set() if args.force else db.competition_ids_with_results(cur)
    todo = [c for c in comps if c["id"] not in already]
    if args.limit:
        todo = todo[: args.limit]
    _log(f"{len(todo)} to load ({len(comps) - len(todo)} skipped/already loaded).")

    loaded = 0
    for i, c in enumerate(todo, 1):
        try:
            page = fetch.competition(c["id"], force=args.refetch)
            detail = parse.parse_competition(page, c["id"])
            # Merge list-level fields that the detail page may lack
            for k in ("name", "meet_date", "sanction_no", "state"):
                if not detail.get(k) and c.get(k):
                    detail[k] = c[k]

            db.upsert_competition(cur, detail)
            # Ensure referenced lifters/teams exist (thin rows; detail filled later)
            for r in detail["results"]:
                if r.get("lifter_id"):
                    db.upsert_lifter(cur, r["lifter_id"], name=r.get("lifter_name"),
                                     birth_year=r.get("yob"), state=r.get("lifter_state"))
                if r.get("team_id"):
                    db.upsert_team(cur, r["team_id"])
            db.replace_results_for_competition(cur, c["id"], detail["results"])
            conn.commit()
            loaded += 1
            _log(f"[{i}/{len(todo)}] comp {c['id']} '{detail['name']}' "
                 f"-> {len(detail['results'])} results")
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            _log(f"[{i}/{len(todo)}] comp {c['id']} FAILED: {e}")
    cur.close()
    conn.close()
    _log(f"Done. Loaded {loaded} competitions.")


def cmd_scrape_lifters(args):
    conn = db.connect()
    cur = conn.cursor()
    todo = sorted(db.lifter_ids_needing_detail(cur))
    if args.limit:
        todo = todo[: args.limit]
    _log(f"{len(todo)} lifters need detail.")
    for i, lid in enumerate(todo, 1):
        try:
            page = fetch.lifter(lid, force=args.refetch)
            l = parse.parse_lifter(page, lid)
            db.upsert_lifter(cur, lid, name=l.get("name"),
                             birth_year=l.get("birth_year"), state=l.get("state"))
            conn.commit()
            if i % 25 == 0 or i == len(todo):
                _log(f"[{i}/{len(todo)}] lifters updated")
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            _log(f"lifter {lid} FAILED: {e}")
    cur.close()
    conn.close()
    _log("Lifters done.")


def cmd_scrape_teams(args):
    conn = db.connect()
    cur = conn.cursor()
    referenced = db.referenced_team_ids(cur)
    cur.execute("SELECT id FROM teams WHERE name IS NULL")
    need = sorted(referenced & {r[0] for r in cur.fetchall()} or referenced)
    if args.limit:
        need = need[: args.limit]
    _log(f"{len(need)} teams to fetch.")
    for i, tid in enumerate(need, 1):
        try:
            page = fetch.team(tid, force=args.refetch)
            t = parse.parse_team(page, tid)
            db.upsert_team(cur, tid, name=t.get("name"))
            conn.commit()
            if i % 25 == 0 or i == len(need):
                _log(f"[{i}/{len(need)}] teams updated")
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            _log(f"team {tid} FAILED: {e}")
    cur.close()
    conn.close()
    _log("Teams done.")


def cmd_scrape_records(args):
    conn = db.connect()
    cur = conn.cursor()
    rows = records_mod.fetch_all_records(force=args.refetch)
    db.insert_records(cur, rows)
    conn.commit()
    cur.close()
    conn.close()
    _log(f"Loaded {len(rows)} records.")


def cmd_stats(args):
    conn = db.connect()
    cur = conn.cursor()
    for tbl in ("competitions", "lifters", "teams", "results", "attempts", "records"):
        cur.execute(f"SELECT count(*) FROM {tbl}")
        _log(f"{tbl:14s}: {cur.fetchone()[0]:>8,}")
    cur.close()
    conn.close()


def cmd_all(args):
    cmd_scrape_competitions(args)
    cmd_scrape_lifters(args)
    cmd_scrape_teams(args)
    cmd_scrape_records(args)
    cmd_stats(args)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("init-db", "scrape-competitions", "scrape-lifters",
                 "scrape-teams", "scrape-records", "all", "stats"):
        sp = sub.add_parser(name)
        sp.add_argument("--limit", type=int, default=0)
        sp.add_argument("--force", action="store_true")
        sp.add_argument("--refetch", action="store_true")

    args = p.parse_args()
    dispatch = {
        "init-db": cmd_init_db,
        "scrape-competitions": cmd_scrape_competitions,
        "scrape-lifters": cmd_scrape_lifters,
        "scrape-teams": cmd_scrape_teams,
        "scrape-records": cmd_scrape_records,
        "all": cmd_all,
        "stats": cmd_stats,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()

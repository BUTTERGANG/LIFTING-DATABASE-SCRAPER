"""Database connection + upsert helpers for the NeonDB target."""
from __future__ import annotations

import os
import pathlib

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

SCHEMA_PATH = pathlib.Path(__file__).parent / "schema.sql"


def _dsn() -> str:
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise SystemExit(
            "DATABASE_URL is not set. Copy .env.example to .env and paste your "
            "NeonDB connection string."
        )
    return dsn


def connect():
    conn = psycopg2.connect(_dsn())
    conn.autocommit = False
    return conn


def init_db(conn):
    with conn.cursor() as cur:
        cur.execute(SCHEMA_PATH.read_text())
    conn.commit()


# --------------------------------------------------------------------------- #
# Upserts
# --------------------------------------------------------------------------- #
def upsert_competition(cur, c: dict):
    cur.execute(
        """
        INSERT INTO competitions (id, name, meet_date, sanction_no, state, meet_director)
        VALUES (%(id)s, %(name)s, %(meet_date)s, %(sanction_no)s, %(state)s, %(meet_director)s)
        ON CONFLICT (id) DO UPDATE SET
            name=EXCLUDED.name, meet_date=EXCLUDED.meet_date,
            sanction_no=EXCLUDED.sanction_no, state=EXCLUDED.state,
            meet_director=EXCLUDED.meet_director, scraped_at=now()
        """,
        {**{k: c.get(k) for k in
            ("id", "name", "meet_date", "sanction_no", "state", "meet_director")}},
    )


def upsert_lifter(cur, lifter_id: int, name: str | None = None,
                  birth_year=None, state=None):
    if lifter_id is None:
        return
    cur.execute(
        """
        INSERT INTO lifters (id, name, birth_year, state)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            name=COALESCE(EXCLUDED.name, lifters.name),
            birth_year=COALESCE(EXCLUDED.birth_year, lifters.birth_year),
            state=COALESCE(EXCLUDED.state, lifters.state),
            scraped_at=now()
        """,
        (lifter_id, name, birth_year, state),
    )


def upsert_team(cur, team_id: int, name: str | None = None):
    if team_id is None:
        return
    cur.execute(
        """
        INSERT INTO teams (id, name) VALUES (%s, %s)
        ON CONFLICT (id) DO UPDATE SET
            name=COALESCE(EXCLUDED.name, teams.name), scraped_at=now()
        """,
        (team_id, name),
    )


def replace_results_for_competition(cur, comp_id: int, results: list[dict]):
    """Delete existing results (cascades to attempts) then reinsert — idempotent."""
    cur.execute("DELETE FROM results WHERE competition_id = %s", (comp_id,))
    for r in results:
        cur.execute(
            """
            INSERT INTO results
                (competition_id, lifter_id, team_id, entry_id, event, division,
                 sex, equipment, weight_class, bodyweight, placement, lifter_name,
                 lifter_state, yob, total, points, bp_points)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (comp_id, r.get("lifter_id"), r.get("team_id"), r.get("entry_id"),
             r.get("event"), r.get("division"), r.get("sex"), r.get("equipment"),
             r.get("weight_class"), r.get("bodyweight"), r.get("placing"),
             r.get("lifter_name"), r.get("lifter_state"), r.get("yob"),
             r.get("total"), r.get("points"), r.get("bp_points")),
        )
        result_id = cur.fetchone()[0]
        for a in r.get("attempts", []):
            cur.execute(
                """
                INSERT INTO attempts
                    (result_id, discipline, attempt_no, weight_kg, is_good, video_id)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (result_id, discipline, attempt_no) DO NOTHING
                """,
                (result_id, a["discipline"], a["attempt_no"], a["weight_kg"],
                 a["is_good"], a["video_id"]),
            )


def existing_competition_ids(cur) -> set[int]:
    cur.execute("SELECT id FROM competitions")
    return {r[0] for r in cur.fetchall()}


def competition_ids_with_results(cur) -> set[int]:
    cur.execute("SELECT DISTINCT competition_id FROM results")
    return {r[0] for r in cur.fetchall()}


def referenced_lifter_ids(cur) -> set[int]:
    cur.execute("SELECT DISTINCT lifter_id FROM results WHERE lifter_id IS NOT NULL")
    return {r[0] for r in cur.fetchall()}


def referenced_team_ids(cur) -> set[int]:
    cur.execute("SELECT DISTINCT team_id FROM results WHERE team_id IS NOT NULL")
    return {r[0] for r in cur.fetchall()}


def lifter_ids_needing_detail(cur) -> set[int]:
    """Lifters referenced by results but never scraped (birth_year still NULL)."""
    cur.execute(
        "SELECT id FROM lifters WHERE birth_year IS NULL"
    )
    return {r[0] for r in cur.fetchall()}


def insert_records(cur, rows: list[dict]):
    cur.execute("TRUNCATE records")
    psycopg2.extras.execute_batch(
        cur,
        """
        INSERT INTO records
            (sex, record_type, category, weight_class, discipline, lifter_name,
             weight_kg, record_date, competition_name, raw_row)
        VALUES (%(sex)s,%(record_type)s,%(category)s,%(weight_class)s,%(discipline)s,
                %(lifter_name)s,%(weight_kg)s,%(record_date)s,%(competition_name)s,
                %(raw_row)s)
        """,
        rows,
    )

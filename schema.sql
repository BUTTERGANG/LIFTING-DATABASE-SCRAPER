-- Powerlifting results schema for pa.liftingdatabase.com -> NeonDB (Postgres)
-- All weights are stored in kilograms (site canonical unit).
-- Site-assigned integer ids are used as primary keys so re-runs upsert cleanly.

CREATE TABLE IF NOT EXISTS competitions (
    id            INTEGER PRIMARY KEY,          -- site competition id
    name          TEXT NOT NULL,
    meet_date     DATE,
    sanction_no   TEXT,
    state         TEXT,
    meet_director TEXT,
    scraped_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS teams (
    id         INTEGER PRIMARY KEY,             -- site club id
    name       TEXT,
    scraped_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS lifters (
    id         INTEGER PRIMARY KEY,             -- site lifter id
    name       TEXT NOT NULL,
    birth_year INTEGER,
    state      TEXT,
    scraped_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per lifter entry in a competition event (a lifter may enter multiple events).
CREATE TABLE IF NOT EXISTS results (
    id             BIGSERIAL PRIMARY KEY,
    competition_id INTEGER NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
    lifter_id      INTEGER REFERENCES lifters(id) ON DELETE SET NULL,
    team_id        INTEGER REFERENCES teams(id) ON DELETE SET NULL,
    entry_id       INTEGER,          -- site entry id (the clickVideo/lift id trailing number)
    event          TEXT,             -- e.g. SBD, BP, DL (competition_view_event header)
    division       TEXT,             -- raw division label, e.g. "Male - Raw Open"
    sex            TEXT,             -- parsed from division: Male/Female
    equipment      TEXT,             -- parsed from division: Raw/Equipped/etc
    weight_class   TEXT,             -- e.g. -93, 120+
    bodyweight     NUMERIC(6,2),
    placement      TEXT,             -- keep as text: "1.", "DQ", "-" (placing is a reserved word)
    lifter_name    TEXT,             -- denormalized as shown on the result row
    lifter_state   TEXT,
    yob            INTEGER,
    total          NUMERIC(7,2),
    points         NUMERIC(8,3),
    bp_points      NUMERIC(8,3),
    scraped_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- entry_id is the site's per-entry natural key. A lifter can legitimately
    -- appear twice in one division (double registration) with distinct entry_ids.
    UNIQUE (competition_id, entry_id)
);

-- One row per individual attempt (up to 9 per result: 3 squat, 3 bench, 3 deadlift).
CREATE TABLE IF NOT EXISTS attempts (
    id          BIGSERIAL PRIMARY KEY,
    result_id   BIGINT NOT NULL REFERENCES results(id) ON DELETE CASCADE,
    discipline  TEXT NOT NULL,       -- squat / bench / deadlift
    attempt_no  SMALLINT NOT NULL,   -- 1..3
    weight_kg   NUMERIC(7,2),        -- NULL if attempt not taken
    is_good     BOOLEAN,             -- TRUE make, FALSE miss, NULL not taken
    video_id    INTEGER,             -- clickVideo id, if any
    UNIQUE (result_id, discipline, attempt_no)
);

-- Records imported from the site CSV export (records-allCSV?sex=m|f).
CREATE TABLE IF NOT EXISTS records (
    id             BIGSERIAL PRIMARY KEY,
    sex            TEXT,
    record_type    TEXT,             -- e.g. "National Raw", "Ohio Raw"
    category        TEXT,            -- division/age category
    weight_class   TEXT,
    discipline     TEXT,             -- Squat/Bench press/Deadlift/Total
    lifter_name    TEXT,
    weight_kg      NUMERIC(7,2),
    record_date    DATE,
    competition_name TEXT,
    raw_row        JSONB,            -- original CSV row for anything not modeled
    scraped_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_competitions_date  ON competitions(meet_date);
CREATE INDEX IF NOT EXISTS idx_results_comp        ON results(competition_id);
CREATE INDEX IF NOT EXISTS idx_results_lifter      ON results(lifter_id);
CREATE INDEX IF NOT EXISTS idx_results_team        ON results(team_id);
CREATE INDEX IF NOT EXISTS idx_attempts_result     ON attempts(result_id);
CREATE INDEX IF NOT EXISTS idx_lifters_name        ON lifters(name);
CREATE INDEX IF NOT EXISTS idx_records_lifter_name ON records(lifter_name);

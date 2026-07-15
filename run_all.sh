#!/bin/bash
# Fully-autonomous full load: competitions -> lifters -> teams -> records -> stats.
# Runs each stage in sequence, logging to full_load.log. Safe to re-run: every
# stage is resumable/idempotent, so a restart skips already-loaded work.
#
# Launch detached (survives terminal close, prevents idle sleep):
#   caffeinate -is nohup ./run_all.sh > full_load.log 2>&1 &
set -u
cd "$(dirname "$0")"
PY=".venv/bin/python"

stamp() { date "+%Y-%m-%d %H:%M:%S"; }
run_stage() {
    local name="$1"; shift
    echo "===== [$(stamp)] START stage: $name ====="
    # Retry a stage up to 3 times if it exits non-zero (transient network/DB blips).
    local attempt=1
    while [ "$attempt" -le 3 ]; do
        if "$PY" run.py "$@"; then
            echo "===== [$(stamp)] DONE stage: $name ====="
            return 0
        fi
        echo "===== [$(stamp)] stage $name failed (attempt $attempt), retrying in 30s ====="
        attempt=$((attempt + 1))
        sleep 30
    done
    echo "===== [$(stamp)] stage $name FAILED after 3 attempts, continuing to next ====="
    return 1
}

echo "########## [$(stamp)] AUTONOMOUS FULL LOAD BEGIN ##########"
run_stage "competitions" scrape-competitions
# Lifter-detail stage is skipped here (long ~4h run at 1 req/sec). Run it separately,
# e.g. on a VPS, with:  .venv/bin/python run.py scrape-lifters
# It only fills birth_year/state for lifters where those are NULL, is resumable,
# and targets the same DATABASE_URL, so it can run any time against this DB.
# run_stage "lifters"      scrape-lifters
run_stage "teams"        scrape-teams
run_stage "records"      scrape-records
echo "########## [$(stamp)] FINAL STATS ##########"
"$PY" run.py stats
echo "########## [$(stamp)] AUTONOMOUS FULL LOAD COMPLETE ##########"

"""Download and parse the site's records CSV export (records-allCSV?sex=m|f)."""
from __future__ import annotations

import csv
import io
import json
import datetime as dt

import fetch


def _date(text: str | None):
    if not text:
        return None
    text = text.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _num(text: str | None):
    if text is None:
        return None
    text = text.strip().replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_records_csv(text: str, sex_hint: str | None = None) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    rows = []
    for raw in reader:
        # Header: type;category;weightclass;discipline;sex;weight;firstname;lastname;dateset;
        clean = {k.strip(): (v.strip() if isinstance(v, str) else v)
                 for k, v in raw.items() if k and k.strip()}
        if not clean.get("type"):
            continue
        first = clean.get("firstname", "") or ""
        last = clean.get("lastname", "") or ""
        name = (first + " " + last).strip() or None
        rows.append({
            "sex": clean.get("sex") or sex_hint,
            "record_type": clean.get("type"),
            "category": clean.get("category") or None,
            "weight_class": clean.get("weightclass") or None,
            "discipline": clean.get("discipline") or None,
            "lifter_name": name,
            "weight_kg": _num(clean.get("weight")),
            "record_date": _date(clean.get("dateset")),
            "competition_name": clean.get("competition") or None,
            "raw_row": json.dumps(clean),
        })
    return rows


def fetch_all_records(force: bool = False) -> list[dict]:
    rows = []
    for sex in ("m", "f"):
        text = fetch.records_csv(sex, force=force)
        rows.extend(parse_records_csv(text, sex_hint=sex))
    return rows

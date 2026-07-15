"""Pure HTML parsers for pa.liftingdatabase.com pages.

No network or DB here — each function takes HTML text and returns plain dicts,
so parsers can be unit-tested against saved fixtures.
"""
from __future__ import annotations

import re
import json
import datetime as dt

from bs4 import BeautifulSoup

DISCIPLINE_BY_NUM = {1: "squat", 2: "bench", 3: "deadlift"}
_LIFT_ID_RE = re.compile(r"lift_(\d+)_(\d+)_(\d+)_(\d+)")
_CLICKVIDEO_RE = re.compile(r"clickVideo\(this,\s*(\d+)\)")
_ID_IN_HREF_RE = re.compile(r"id=(\d+)")


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _num(text: str | None):
    if not text:
        return None
    text = text.strip().replace(",", "")
    if text in ("", "-", "—"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _int(text: str | None):
    v = _num(text)
    return int(v) if v is not None else None


def _date(text: str | None):
    if not text:
        return None
    text = text.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _href_id(a_tag) -> int | None:
    if not a_tag or not a_tag.get("href"):
        return None
    m = _ID_IN_HREF_RE.search(a_tag["href"])
    if not m:
        return None
    val = int(m.group(1))
    # The site uses id=0 as a "no team / no lifter" placeholder; treat as NULL.
    return val if val > 0 else None


# --------------------------------------------------------------------------- #
# Competition list
# --------------------------------------------------------------------------- #
def parse_competition_list(html: str) -> list[dict]:
    """Return [{id, name, meet_date, sanction_no, state, has_results}] for every meet."""
    soup = _soup(html)
    out = []
    seen = set()
    for a in soup.select('a[href^="competitions-view?id="]'):
        cid = _href_id(a)
        if cid is None or cid in seen:
            continue
        row = a.find_parent("tr")
        rec = {"id": cid, "name": a.get_text(strip=True),
               "meet_date": None, "sanction_no": None, "state": None,
               "has_results": False}
        if row:
            cells = row.find_all("td")
            if len(cells) >= 4:
                rec["meet_date"] = _date(cells[0].get_text())
                rec["sanction_no"] = cells[2].get_text(strip=True) or None
                rec["state"] = cells[3].get_text(strip=True) or None
                rec["has_results"] = bool(row.find("img", src=re.compile("check")))
        seen.add(cid)
        out.append(rec)
    return out


# --------------------------------------------------------------------------- #
# Competition (header + results table)
# --------------------------------------------------------------------------- #
def _split_division(division: str):
    """"Male - Raw Open" -> (sex, equipment). Best-effort."""
    sex = equip = None
    if not division:
        return sex, equip
    low = division.lower()
    if low.startswith("female") or low.startswith("women") or low.startswith("f "):
        sex = "Female"
    elif low.startswith("male") or low.startswith("men") or low.startswith("m "):
        sex = "Male"
    for eq in ("Raw", "Equipped", "Classic", "Single-ply", "Multi-ply", "Wraps",
               "Unlimited"):
        if eq.lower() in low:
            equip = eq
            break
    return sex, equip


def parse_competition(html: str, comp_id: int) -> dict:
    soup = _soup(html)
    content = soup.find("div", id="content")
    comp = {"id": comp_id, "name": None, "meet_date": None,
            "sanction_no": None, "state": None, "meet_director": None}

    h3 = content.find("h3") if content else None
    if h3:
        comp["name"] = h3.get_text(strip=True)
    # Header table: <th>label</th><td>value</td>
    if content:
        for tr in content.find_all("tr"):
            th, td = tr.find("th"), tr.find("td")
            if not th or not td:
                continue
            label = th.get_text(strip=True).rstrip(":").lower()
            val = td.get_text(strip=True)
            if label == "date":
                comp["meet_date"] = _date(val)
            elif label.startswith("sanction"):
                comp["sanction_no"] = val or None
            elif label == "state":
                comp["state"] = val or None
            elif label.startswith("meet director"):
                comp["meet_director"] = val or None

    results = []
    table = soup.find("table", id="competition_view_results")
    if not table:
        comp["results"] = results
        return comp

    current_event = None
    current_division = None
    body = table.find("tbody") or table
    for tr in body.find_all("tr", recursive=False):
        # Header rows: a single th with colspan
        ths = tr.find_all("th", recursive=False)
        if ths and (not tr.find("td", recursive=False)):
            th = ths[0]
            classes = th.get("class") or []
            txt = th.get_text(strip=True)
            if "competition_view_event" in classes:
                current_event = txt or None
            elif txt:
                current_division = txt
            continue

        tds = tr.find_all("td", recursive=False)
        if len(tds) < 7:
            continue

        name_cell = None
        for td in tds:
            if td.get("id", "").startswith("lifter_") or td.find("a", href=re.compile(r"lifters-view")):
                name_cell = td
                break
        if name_cell is None:
            continue

        lifter_a = name_cell.find("a", href=re.compile(r"lifters-view"))
        lifter_id = _href_id(lifter_a)
        lifter_name = lifter_a.get_text(strip=True) if lifter_a else name_cell.get_text(strip=True)

        # Fixed leading columns: weightclass, placing, name, yob, team, state, weight
        weight_class = tds[0].get_text(strip=True) or None
        placing = tds[1].get_text(strip=True) or None
        yob = _int(tds[3].get_text()) if len(tds) > 3 else None
        team_a = tds[4].find("a", href=re.compile(r"clubs-view")) if len(tds) > 4 else None
        team_id = _href_id(team_a)
        lifter_state = tds[5].get_text(strip=True) if len(tds) > 5 else None
        bodyweight = _num(tds[6].get_text()) if len(tds) > 6 else None

        # Attempt cells carry id="lift_{lifter}_{slot}_{disc}_{entry}"
        attempts = []
        entry_id = None
        for td in tds:
            tid = td.get("id", "")
            m = _LIFT_ID_RE.match(tid)
            if not m:
                continue
            _lifter, slot, disc, entry = (int(g) for g in m.groups())
            entry_id = entry
            discipline = DISCIPLINE_BY_NUM.get(disc)
            if discipline is None:
                continue
            attempt_no = ((slot - 1) % 3) + 1
            classes = td.get("class") or []
            weight = _num(td.get_text())
            is_good = None
            if "lift_good" in classes:
                is_good = True
            elif "lift_fail" in classes:
                is_good = False
            vid = None
            vm = _CLICKVIDEO_RE.search(td.get("onclick", "") or "")
            if vm:
                vid = int(vm.group(1))
            attempts.append({
                "discipline": discipline, "attempt_no": attempt_no,
                "weight_kg": weight, "is_good": is_good, "video_id": vid,
            })

        # Trailing summary columns: total, points, bp_points (the last 3 plain <td>)
        summary = [td for td in tds if not _LIFT_ID_RE.match(td.get("id", ""))]
        total = points = bp_points = None
        if len(summary) >= 3:
            # summary tail = [..., total, points, bp_points, (maybe blanks)]
            nums = [td.get_text(strip=True) for td in summary[7:]]
            nums = [n for n in nums if n != ""]
            if len(nums) >= 1:
                total = _num(nums[0])
            if len(nums) >= 2:
                points = _num(nums[1])
            if len(nums) >= 3:
                bp_points = _num(nums[2])

        sex, equipment = _split_division(current_division or "")
        results.append({
            "lifter_id": lifter_id, "lifter_name": lifter_name,
            "team_id": team_id, "entry_id": entry_id,
            "event": current_event, "division": current_division,
            "sex": sex, "equipment": equipment,
            "weight_class": weight_class, "bodyweight": bodyweight,
            "placing": placing, "lifter_state": lifter_state, "yob": yob,
            "total": total, "points": points, "bp_points": bp_points,
            "attempts": attempts,
        })

    comp["results"] = results
    return comp


# --------------------------------------------------------------------------- #
# Lifter
# --------------------------------------------------------------------------- #
def parse_lifter(html: str, lifter_id: int) -> dict:
    soup = _soup(html)
    content = soup.find("div", id="content")
    rec = {"id": lifter_id, "name": None, "birth_year": None, "state": None,
           "history": []}
    if content:
        h2 = content.find("h2")
        if h2:
            name = h2.get_text(strip=True)
            rec["name"] = re.sub(r"^Lifter\s*-\s*", "", name).strip() or None
        for tr in content.find_all("tr"):
            th, td = tr.find("th"), tr.find("td")
            if not th or not td:
                continue
            label = th.get_text(strip=True).rstrip(":").lower()
            val = td.get_text(strip=True)
            if label.startswith("birth"):
                rec["birth_year"] = _int(val)
            elif label == "state":
                rec["state"] = val or None
    # Result history is in a graphData JS object
    for m in re.finditer(r"var graphData\s*=\s*(\{.*?\});", html, re.DOTALL):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        for discipline, points in data.items():
            for p in points:
                rec["history"].append({
                    "discipline": discipline,
                    "weight_kg": p.get("y"),
                    "competition_id": _int(str(p.get("competitionid"))),
                    "competition_name": p.get("competitionname"),
                    "place": p.get("place"),
                })
    return rec


# --------------------------------------------------------------------------- #
# Team
# --------------------------------------------------------------------------- #
def parse_team(html: str, team_id: int) -> dict:
    soup = _soup(html)
    content = soup.find("div", id="content")
    name = None
    if content:
        h2 = content.find("h2")
        if h2:
            name = re.sub(r"^(Team|Club)\s*-\s*", "", h2.get_text(strip=True)).strip()
        if not name:
            h3 = content.find("h3")
            if h3:
                name = h3.get_text(strip=True)
    return {"id": team_id, "name": name or None}

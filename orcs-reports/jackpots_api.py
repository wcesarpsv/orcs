"""Extract next-draw Lotto Max and Gold Ball from the Loto-Québec HTML.

No JavaScript browser required. Reject ambiguous values and dates.
"""
import re
from datetime import date
from bs4 import BeautifulSoup

SOURCE = "https://loteries.lotoquebec.com/en/lotteries"
MONTHS = {name.lower(): i for i, name in enumerate(
    ("January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"), 1)}
DATE_RE = re.compile(
    r"\b(?:(?:This\s+)?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)|Tonight|Tomorrow),?\s+"
    r"(" + "|".join(MONTHS) + r")\s+(\d{1,2}),?\s+(20\d{2})\b", re.I
)
AMOUNT_RE = re.compile(r"\$\s*([\d,]+)\s*million\b", re.I)
COUNT_RE = re.compile(r"\b(\d+)\s+Maxmillions\b", re.I)

def _unique(items):
    unique = set(items)
    return next(iter(unique)) if len(unique) == 1 else None

def _date_from_match(match):
    if not match:
        return None
    try:
        return date(int(match.group(3)), MONTHS[match.group(1).lower()], int(match.group(2))).isoformat()
    except ValueError:
        return None

def parse_jackpots(html):
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "nav", "footer", "header"]):
        element.decompose()
    text = " ".join(soup.stripped_strings)
    text = re.sub(r"\s+", " ", text)

    # Dates anchor the cards, avoiding navigation headings and historic draws.
    # Both next-draw cards have a weekday; Lotto Max has "Maxmillions",
    # while Lotto 6/49 has "The Gold Ball" and "The Classic".
    blocks = []
    dates = list(DATE_RE.finditer(text))
    for i, match in enumerate(dates):
        next_start = dates[i + 1].start() if i + 1 < len(dates) else len(text)
        blocks.append((match, text[match.end():min(next_start, match.end() + 500)]))

    max_candidates = []
    gold_candidates = []
    for draw_match, block in blocks:
        # Gold Ball is the other draw card; never mistake its prize for Lotto Max.
        is_gold_card = bool(re.search(r"\\bThe\\s+Gold\\s+Ball\\b", block, re.I))
        if not is_gold_card:
            amounts = AMOUNT_RE.findall(block)
            max_counts = COUNT_RE.findall(block)
            # Without Maxmillions, Loto-Québec shows e.g. "10 x $100,000".
            # This is NOT a Maxmillions count. Only a complete, dated
            # Lotto Max card can establish a zero count.
            if len(amounts) == 1 and len(set(max_counts)) <= 1:
                max_candidates.append((
                    _date_from_match(draw_match),
                    int(amounts[0].replace(",", "")),
                    int(max_counts[0]) if max_counts else 0,
                ))
        gold_label = re.search(r"\bThe\s+Gold\s+Ball\b", block, re.I)
        if gold_label:
            tail = block[gold_label.end():]
            classic = re.search(r"\bThe\s+Classic\b", tail, re.I)
            gold_area = tail[:classic.start()] if classic else tail[:100]
            amounts = AMOUNT_RE.findall(gold_area)
            if amounts:
                gold_candidates.append((_date_from_match(draw_match), int(amounts[0].replace(",", ""))))

    max_result = _unique(max_candidates)
    gold_result = _unique(gold_candidates)
    # Confirm both game names occur on the source page.
    if not re.search(r"\bLotto\s+Max\b", text, re.I):
        max_result = None
    if not re.search(r"\bLotto\s+6/49\b", text, re.I):
        gold_result = None
    return {
        "values": {
            "lotto_max": max_result[1] if max_result else None,
            "gold_ball": gold_result[1] if gold_result else None,
            "maxmillions": max_result[2] if max_result else None,
        },
        "draw_dates": {
            "lotto_max": max_result[0] if max_result else None,
            "gold_ball": gold_result[0] if gold_result else None,
        },
    }


from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import requests

VALID_SECONDS = 300

def snapshot(html, now=None):
    now = now or datetime.now(timezone.utc)
    parsed = parse_jackpots(html)
    values, dates = parsed["values"], parsed["draw_dates"]
    today = now.astimezone(ZoneInfo("America/Toronto")).date()
    errors = []
    for key in ("lotto_max", "gold_ball", "maxmillions"):
        v = values.get(key)
        minimum = 0 if key == "maxmillions" else 1
        if type(v) is not int or not minimum <= v <= 200:
            errors.append(key + ": invalid or missing")
    for key in ("lotto_max", "gold_ball"):
        try:
            d = date.fromisoformat(dates.get(key) or "")
            if not today <= d <= today + timedelta(days=8):
                errors.append(key + ": stale draw date")
        except ValueError:
            errors.append(key + ": invalid draw date")
    allowed = not errors
    return {
        "schema_version": 1, "status": "ok" if allowed else "unverified",
        "transmit_allowed": allowed,
        "values": values if allowed else dict.fromkeys(("lotto_max", "gold_ball", "maxmillions")),
        "draw_dates": dates, "checked_at": now.isoformat(timespec="seconds"),
        "generated_at_unix": int(now.timestamp()),
        "expires_at_unix": int(now.timestamp()) + (VALID_SECONDS if allowed else 0),
        "maxmillions_mode": "extracted", "source": SOURCE,
        "served_by": "orcs-reports.vercel.app", "errors": errors,
    }

def unavailable(message):
    now = datetime.now(timezone.utc)
    return {
        "schema_version": 1, "status": "unavailable", "transmit_allowed": False,
        "values": dict.fromkeys(("lotto_max", "gold_ball", "maxmillions")),
        "draw_dates": {}, "checked_at": now.isoformat(timespec="seconds"),
        "generated_at_unix": int(now.timestamp()), "expires_at_unix": int(now.timestamp()),
        "maxmillions_mode": "extracted", "source": SOURCE,
        "served_by": "orcs-reports.vercel.app", "errors": [message],
    }

def register_routes(app):
    from flask import jsonify
    @app.get("/api/jackpots")
    def jackpots():
        try:
            response = requests.get(SOURCE, headers={
                "User-Agent": "Mozilla/5.0 (ORCS Jackpot API/1.0)",
                "Accept-Language": "en-CA,en;q=0.9",
            }, timeout=(5, 12))
            response.raise_for_status()
            if len(response.content) > 2_000_000:
                raise ValueError("Source response too large")
            response.encoding = "utf-8"
            data = snapshot(response.text)
        except Exception as exc:
            data = unavailable("Source fetch failed: " + type(exc).__name__)
        result = jsonify(data)
        result.headers["Cache-Control"] = "no-store, max-age=0"
        return result

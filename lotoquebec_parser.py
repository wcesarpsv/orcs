"""Validated next-draw jackpot extraction from Loto-Québec's English lotteries page."""
import re
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

SOURCE = "https://loteries.lotoquebec.com/en/lotteries"
MONTHS = {name.lower(): i for i, name in enumerate(
    ("January","February","March","April","May","June","July","August","September","October","November","December"), 1)}
DATE_RE = re.compile(r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2}),?\s+(20\d{2})\b", re.I)

def _draw_date(text):
    m = DATE_RE.search(text)
    if not m:
        return None
    try:
        return date(int(m[3]), MONTHS[m[1].lower()], int(m[2])).isoformat()
    except ValueError:
        return None

def _unique(pattern, text):
    matches = re.findall(pattern, text, re.I)
    values = {int(v.replace(",", "")) for v in matches}
    return next(iter(values)) if len(values) == 1 else None

def parse_jackpots(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    # Restrict extraction to the two game panels. Never use other lotteries'
    # amounts, past results, or the classic $5M as Gold Ball.
    max_start = re.search(r"\bLotto Max\b", text, re.I)
    six_start = re.search(r"\bLotto 6/49\b", text, re.I)
    if not max_start or not six_start or max_start.end() >= six_start.start():
        return {"values": {"lotto_max": None, "gold_ball": None, "maxmillions": None},
                "draw_dates": {}, "errors": ["Game panels missing or reordered"]}
    max_block = text[max_start.end():six_start.start()]
    rest = text[six_start.end():]
    end = re.search(r"\bLotto Poker\b|\bProgressive Jackpot\b|\bLotteries newsletter\b", rest, re.I)
    gold_block = rest[:end.start()] if end else rest[:400]
    gold_marker = re.search(r"\bGold Ball\b", gold_block, re.I)
    gold_amount = gold_block[gold_marker.end():] if gold_marker else ""
    gold_amount = re.split(r"\bThe Classic\b", gold_amount, maxsplit=1, flags=re.I)[0]
    maximum = _unique(r"\$\s*([\d,]+)\s*million\b", max_block)
    count = _unique(r"\b(\d+)\s*Maxmillions\b", max_block)
    # A missing Maxmillions count is unknown, NOT zero.
    gold = _unique(r"\$\s*([\d,]+)\s*million\b", gold_amount)
    return {
        "values": {"lotto_max": maximum, "gold_ball": gold, "maxmillions": count},
        "draw_dates": {"lotto_max": _draw_date(max_block), "gold_ball": _draw_date(gold_block)},
        "errors": [],
    }

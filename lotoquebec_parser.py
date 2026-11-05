"""Extract the current Loto-Québec jackpot cards without mixing other games.

Reject missing, ambiguous, or malformed fields; the publisher independently checks
integer ranges and draw-date freshness before enabling the ESP32-C6 feed.
"""
import re
from datetime import date
from bs4 import BeautifulSoup

SOURCE = "https://loteries.lotoquebec.com/en/lotteries"
MONTHS = {name.lower(): i for i, name in enumerate(
    ("January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"), 1)}
DATE_PATTERN = r"(?:This\\s+)?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\\s+(" + "|".join(MONTHS) + r")\\s+(\\d{1,2}),?\\s+(20\\d{2})"
MONEY = r"\\$\\s*([\\d,]+)\\s*million\\b"

def _date(month, day, year):
    try:
        return date(int(year), MONTHS[month.lower()], int(day)).isoformat()
    except (ValueError, KeyError):
        return None

def _single(matches):
    unique = set(matches)
    return next(iter(unique)) if len(unique) == 1 else None

def parse_jackpots(html):
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "nav", "footer", "header"]):
        element.decompose()
    text = " ".join(soup.stripped_strings)
    text = re.sub(r"\\s+", " ", text)

    # The current homepage has a Lotto Max next-draw card followed by a
    # Lotto 6/49 next-draw card. Search for the card's date/amount together
    # rather than relying on the first game name (also present in menus).
    max_re = re.compile(DATE_PATTERN + r"\\s+" + MONEY +
        r"\\s+(\\d+)\\s+Maxmillions\\b", re.I)
    max_matches = max_re.findall(text)
    # Gold Ball can have an image alt label before its heading.
    gold_re = re.compile(DATE_PATTERN +
        r".{0,180}?\\bThe\\s+Gold\\s+Ball\\b\\s+" + MONEY, re.I)
    gold_matches = gold_re.findall(text)

    maximum = _single([int(m[3].replace(",", "")) for m in max_matches])
    count = _single([int(m[4]) for m in max_matches])
    gold = _single([int(m[3].replace(",", "")) for m in gold_matches])
    max_date = _single([_date(*m[:3]) for m in max_matches])
    gold_date = _single([_date(*m[:3]) for m in gold_matches])

    # Prevent accidentally accepting a jackpot from an unrelated lottery:
    # require the corresponding game labels on the same page.
    if not re.search(r"\\bLotto\\s+Max\\b", text, re.I):
        maximum = count = max_date = None
    if not re.search(r"\\bLotto\\s+6/49\\b", text, re.I):
        gold = gold_date = None
    return {
        "values": {"lotto_max": maximum, "gold_ball": gold, "maxmillions": count},
        "draw_dates": {"lotto_max": max_date, "gold_ball": gold_date},
    }

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
        max_counts = COUNT_RE.findall(block)
        if max_counts:
            amounts = AMOUNT_RE.findall(block[:COUNT_RE.search(block).start()])
            if amounts:
                max_candidates.append((_date_from_match(draw_match), int(amounts[-1].replace(",", "")), int(max_counts[0])))
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

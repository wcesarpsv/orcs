"""Read upcoming Canadian jackpots from Lottery Post, excluding past results."""
import re
from datetime import date
from decimal import Decimal
from bs4 import BeautifulSoup

# Explicit temporary policy; do not read counts from historical results links.
# Validate a real upcoming-count example before enabling automatic extraction.
MAXMILLIONS_DEFAULT = 0
MONTHS = {name: i for i, name in enumerate(
    ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'), 1)}


def parse_jackpots(html):
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'nav', 'footer']):
        tag.decompose()
    candidates = {'lotto_max': [], 'gold_ball': []}
    for block in soup.select('.resultsdrawing'):
        heading = block.find('h2')
        name = heading.get_text(' ', strip=True) if heading else ''
        key = {'Lotto Max': 'lotto_max', 'Canada Lotto 6/49': 'gold_ball'}.get(name)
        if key is None:
            continue
        dates = block.select('.resultsnextdate')
        amounts = block.select('.resultsJackpotAmount')
        if len(dates) != 1 or len(amounts) != 1:
            candidates[key].append(None)
            continue
        upcoming = dates[0].get_text(' ', strip=True)
        money = amounts[0].get_text(' ', strip=True)
        label = 'Next Jackpot:' if key == 'lotto_max' else 'Next Gold Ball Jackpot:'
        match = re.fullmatch(
            r'[A-Za-z]{3},\s*([A-Za-z]{3})\s+(\d{1,2}),\s*(\d{4}),\s*\d{1,2}:\d{2}\s*[ap]m',
            upcoming, re.I)
        dollars = re.findall(r'CA\$\s*([\d,]+(?:\.\d+)?)\s+Million\b', money, re.I)
        try:
            draw = date(int(match[3]), MONTHS[match[1].title()], int(match[2])).isoformat()
            value = Decimal(dollars[0].replace(',', ''))
            if not money.startswith(label) or len(dollars) != 1 or value != int(value):
                raise ValueError('Ambiguous or nonintegral jackpot')
            candidates[key].append((draw, int(value), f'{upcoming} | {money}'))
        except (TypeError, KeyError, ValueError, IndexError):
            candidates[key].append(None)

    def unique(items):
        if not items or None in items or len({x[:2] for x in items}) != 1:
            return None
        return items[0]

    m, g = (unique(candidates[key]) for key in ('lotto_max', 'gold_ball'))
    return {
        'values': {'lotto_max': m[1] if m else None,
                   'gold_ball': g[1] if g else None,
                   'maxmillions': MAXMILLIONS_DEFAULT if m else None},
        'draw_dates': {'lotto_max': m[0] if m else None, 'gold_ball': g[0] if g else None},
        'evidence': {'lotto_max': m[2] if m else None, 'gold_ball': g[2] if g else None},
        'excerpt': soup.get_text(' ', strip=True)[:1200],
    }

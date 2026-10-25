"""Parse identified next-jackpot panels on OLG's simplified Chinese site."""
import re
import unicodedata
from datetime import date
from decimal import Decimal
from bs4 import BeautifulSoup

MAXMILLIONS_DEFAULT = 0  # Explicit temporary policy requested for this feed.


def amount_millions(text):
    text = unicodedata.normalize('NFKC', text)
    dollars = re.findall(r'\$\s*([\d,]+(?:\.\d+)?)', text)
    chinese = re.findall(r'(\d+(?:\.\d+)?)\s*(千万元|百万元|亿元|万元)', text)
    values = [Decimal(x.replace(',', '')) / 1_000_000 for x in dollars]
    factors = {'千万元': 10, '百万元': 1, '亿元': 100, '万元': Decimal('0.01')}
    values += [Decimal(number) * factors[unit] for number, unit in chinese]
    if not values or len(set(values)) != 1 or values[0] != int(values[0]):
        return None
    return int(values[0])


def parse_jackpots(html):
    soup = BeautifulSoup(html, 'html.parser')
    for node in soup(['script', 'style', 'nav', 'footer']):
        node.decompose()
    candidates = {'lotto_max': [], 'gold_ball': []}
    for panel in soup.select('.slide, .block'):
        images = ' '.join(str(img.get('src', '')).lower() for img in panel.find_all('img'))
        classes = panel.get('class', [])
        if 'max' in classes or re.search(r'(?:logo-max|max-logo|home_jackport_btn_big_max)\.', images):
            key = 'lotto_max'
        elif 'banner649' in classes or re.search(r'logo-649\.', images):
            key = 'gold_ball'
        else:
            continue
        texts = panel.select('.text')
        dates = panel.select('.text .title time[datetime]')
        parsed = None
        if len(texts) == 1 and len(dates) == 1:
            try:
                draw = date.fromisoformat(dates[0]['datetime']).isoformat()
                # Machine-readable date and visible date must agree.
                visible = re.search(r'(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日', dates[0].get_text())
                if not visible or date(*map(int, visible.groups())).isoformat() != draw:
                    raise ValueError('Conflicting date')
                if key == 'gold_ball':
                    gold = texts[0].select('img.goldBall, img[src*="goldball"]')
                    amounts = gold[0].parent.select('h2, .price') if len(gold) == 1 else []
                else:
                    amounts = texts[0].select('h2, .price')
                if len(amounts) == 1:
                    evidence = amounts[0].get_text(' ', strip=True)
                    value = amount_millions(evidence)
                    if value is not None:
                        parsed = (draw, value, evidence)
            except ValueError:
                pass
        candidates[key].append(parsed)

    def unique(items):
        # Never silently choose between conflicting banner and jackpot cards.
        if not items or None in items or len({x[:2] for x in items}) != 1:
            return None
        return items[0]

    m, g = (unique(candidates[k]) for k in ('lotto_max', 'gold_ball'))
    return {
        'values': {'lotto_max': m[1] if m else None, 'gold_ball': g[1] if g else None,
                   'maxmillions': MAXMILLIONS_DEFAULT if m else None},
        'draw_dates': {'lotto_max': m[0] if m else None, 'gold_ball': g[0] if g else None},
        'evidence': {'lotto_max': m[2] if m else None, 'gold_ball': g[2] if g else None},
        'excerpt': soup.get_text(' ', strip=True)[:1200],
    }

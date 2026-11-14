"""Read identified next-draw lottery cards from Loto-Quebec HTML."""
import re
from datetime import date
from bs4 import BeautifulSoup
SOURCE='https://loteries.lotoquebec.com/en/lotteries'
MONTHS={m.lower():i for i,m in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'),1)}
DATE_RE=re.compile(r'\b(?:(?:This\s+)?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)|Tonight|Tomorrow),?\s+('+'|'.join(MONTHS)+r')\s+(\d{1,2}),?\s+(20\d{2})\b',re.I)
AMOUNT_RE=re.compile(r'\$\s*([\d,]+)\s*million\b',re.I)
COUNT_RE=re.compile(r'\b(\d+)\s+Maxmillions\b',re.I)

def unique(items):
    values=set(items)
    return next(iter(values)) if len(values)==1 else None

def parse_jackpots(html):
    soup=BeautifulSoup(html,'html.parser')
    for n in soup(['script','style','nav','footer','header']):n.decompose()
    candidates={'lotto_max':[],'gold_ball':[]}
    # An exact game logo anchors each card; other games or navigation cannot fill missing values.
    for img in soup.find_all('img'):
        alt=re.sub(r'\s+',' ',str(img.get('alt','')).strip()).lower()
        key={'lotto max':'lotto_max','lotto 6/49':'gold_ball'}.get(alt)
        if not key:continue
        card=img
        for _ in range(8):
            card=card.parent
            if card is None:break
            text=' '.join(card.stripped_strings)
            dates=list(DATE_RE.finditer(text))
            if not dates:continue
            # Never ascend into a container with several games or draw dates.
            if len(dates)!=1:break
            game_logos=[n for n in card.find_all('img') if str(n.get('alt','')).lower() in ('lotto max','lotto 6/49')]
            if len(game_logos)!=1:break
            match=dates[0]
            try:draw=date(int(match[3]),MONTHS[match[1].lower()],int(match[2])).isoformat()
            except ValueError:draw=None
            if key=='gold_ball':
                label=re.search(r'\bThe\s+Gold\s+Ball\b',text,re.I)
                if not label:continue
                tail=text[label.end():];classic=re.search(r'\bThe\s+Classic\b',tail,re.I)
                area=tail[:classic.start()] if classic else tail
                amounts=AMOUNT_RE.findall(area)
                if len(amounts)!=1:candidates[key].append((None,None));break
                candidates[key].append((draw,int(amounts[0].replace(',',''))));break
            amounts=AMOUNT_RE.findall(text)
            if not amounts:continue
            counts=COUNT_RE.findall(text)
            if len(amounts)!=1 or len(set(counts))>1:
                candidates[key].append((None,None,None));break
            candidates[key].append((draw,int(amounts[0].replace(',','')),int(counts[0]) if counts else 0));break
    maximum=unique(candidates['lotto_max']);gold=unique(candidates['gold_ball'])
    return {'values':{'lotto_max':maximum[1] if maximum else None,'gold_ball':gold[1] if gold else None,'maxmillions':maximum[2] if maximum else None},'draw_dates':{'lotto_max':maximum[0] if maximum else None,'gold_ball':gold[0] if gold else None}}

#!/usr/bin/env python3
"""Archive NBA official scoreboard to GitHub Pages. Never touches Google Sheets."""
import json, os, pathlib, urllib.request, datetime, sys
from zoneinfo import ZoneInfo
BASE=pathlib.Path('docs/scores'); BASE.mkdir(parents=True,exist_ok=True)
URL='https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json'
req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json','Referer':'https://www.nba.com/'})
try:
    with urllib.request.urlopen(req,timeout=25) as response:
        if response.status!=200: raise ValueError(f'HTTP {response.status}')
        payload=json.load(response)
    raw=payload.get('scoreboard',{}).get('games')
    if not isinstance(raw,list): raise ValueError('No scoreboard.games list in response')
except Exception as e:
    print('Score feed unavailable; retaining existing archived scores:',e)
    sys.exit(1)

def et_date(g):
    t=g.get('gameTimeUTC') or g.get('gameTimeUTCISO')
    if not t: return datetime.datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    return datetime.datetime.fromisoformat(t.replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York')).date().isoformat()

def team(t): return ' '.join(str(t.get(k,'')).strip() for k in ('teamCity','teamName')).strip()

def score(g):
    a,h=g.get('awayTeam',{}),g.get('homeTeam',{})
    status=int(g.get('gameStatus') or 1)
    return {'away':team(a),'home':team(h),'awayScore':str(a.get('score','')) if status!=1 else '',
      'homeScore':str(h.get('score','')) if status!=1 else '',
      'state':'post' if status==3 else 'in' if status==2 else 'pre',
      'detail':g.get('gameStatusText',''),'period':int(g.get('period') or 0),
      'completed':status==3,'start':g.get('gameTimeUTC',''),'gameId':str(g.get('gameId',''))}

now=datetime.datetime.now(datetime.timezone.utc).isoformat()
groups={}
for g in raw:
    day=et_date(g); groups.setdefault(day,[]).append(score(g))
if not groups: print('No games in live feed; preserving previous archive'); sys.exit(0)
for day,games in groups.items():
    path=BASE/f'{day}.json'
    # Preserve final scores if the live feed later omits them; avoid replacing nonempty days with partial lists.
    old={}
    if path.exists():
        try: old={g['gameId']:g for g in json.loads(path.read_text()).get('games',[]) if g.get('gameId')}
        except (ValueError,KeyError,TypeError): pass
    for g in games:
        key=g.get('gameId')
        if key: old[key]=g
    output={'available':True,'provider':'NBA via GitHub','date':day,'updated':now,'games':list(old.values())}
    path.write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n')
    print(day,len(output['games']),'games')

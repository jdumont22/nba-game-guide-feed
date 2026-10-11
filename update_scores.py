
#!/usr/bin/env python3
"""BALLDONTLIE free-tier game scores -> existing GitHub Pages JSON format."""
import datetime as dt
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

KEY = os.environ.get('BALLDONTLIE_API_KEY', '').strip()
if not KEY:
    raise SystemExit('Missing GitHub Actions secret BALLDONTLIE_API_KEY')

ROOT = Path('docs/scores')
ROOT.mkdir(parents=True, exist_ok=True)

ET = ZoneInfo('America/New_York')
today = dt.datetime.now(ET).date()
days = [(today + dt.timedelta(days=n)).isoformat() for n in (-1, 0, 1)]


def fetch(season_type=None):
    params = [('per_page', '100')] + [('dates[]', day) for day in days]
    if season_type:
        params.append(('season_type', season_type))

    url = 'https://api.balldontlie.io/v1/games?' + urlencode(params)
    games = []
    cursor = None

    for _ in range(5):
        query_url = url + (('&cursor=' + str(cursor)) if cursor else '')
        req = Request(
            query_url,
            headers={
                'Authorization': KEY,
                'Accept': 'application/json'
            }
        )

        with urlopen(req, timeout=30) as response:
            payload = json.load(response)

        if not isinstance(payload.get('data'), list):
            raise ValueError('BALLDONTLIE returned no data list')

        games.extend(payload['data'])
        cursor = (payload.get('meta') or {}).get('next_cursor')

        if not cursor:
            break
    else:
        raise ValueError('Pagination limit exceeded')

    return games


def normalize(g):
    a = g.get('visitor_team') or {}
    h = g.get('home_team') or {}

    state = str(g.get('status_state') or '').lower()

    if state == 'final':
        stage = 'post'
    elif state == 'in_progress':
        stage = 'in'
    else:
        stage = 'pre'

    return {
        'away': a.get('full_name') or (
            str(a.get('city', '')) + ' ' + str(a.get('name', ''))
        ).strip(),

        'home': h.get('full_name') or (
            str(h.get('city', '')) + ' ' + str(h.get('name', ''))
        ).strip(),

        'awayScore': (
            str(g.get('visitor_team_score'))
            if stage != 'pre' and g.get('visitor_team_score') is not None
            else ''
        ),

        'homeScore': (
            str(g.get('home_team_score'))
            if stage != 'pre' and g.get('home_team_score') is not None
            else ''
        ),

        'state': stage,
        'detail': str(g.get('status') or ''),
        'period': int(g.get('period') or 0),

        # Time remaining in the current quarter, e.g. "5:42".
        # Only include it while the game is in progress.
        'clock': (
            str(g.get('time') or '').strip()
            if stage == 'in'
            else ''
        ),

        'completed': stage == 'post',
        'start': g.get('datetime') or '',
        'gameId': str(g.get('id') or ''),
        'cupStage': g.get('ist_stage'),
    }


# Two requests on ordinary days; the API excludes preseason
# unless explicitly requested.
# Both responses must succeed before publishing anything.

regular = fetch()
preseason = fetch('preseason')

unique = {
    str(g['id']): g
    for g in regular + preseason
    if g.get('id') is not None
}

groups = {}

for g in unique.values():
    stamp = g.get('datetime')

    if stamp:
        try:
            date = dt.datetime.fromisoformat(
                stamp.replace('Z', '+00:00')
            ).astimezone(ET).date().isoformat()
        except ValueError:
            date = g.get('date')
    else:
        date = g.get('date')

    if date:
        groups.setdefault(date, []).append(normalize(g))


now = dt.datetime.now(dt.timezone.utc).isoformat()

for date, new_games in groups.items():
    path = ROOT / (date + '.json')
    old = {}

    if path.exists():
        try:
            old = {
                str(item['gameId']): item
                for item in json.loads(path.read_text()).get('games', [])
                if item.get('gameId')
            }
        except (ValueError, TypeError, KeyError):
            old = {}

    for game in new_games:
        old[game['gameId']] = game

    data = {
        'available': True,
        'provider': 'BALLDONTLIE via GitHub',
        'date': date,
        'updated': now,
        'games': list(old.values())
    }

    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + '\n'
    )

    print(date, len(data['games']), 'games archived')

print('Feed succeeded; total records:', len(unique))

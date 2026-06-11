"""MLB Stats API client (statsapi.mlb.com, free / unauthenticated).

Provides today's Cubs game, NL Central standings, and the next game with
probable pitchers. Cubs teamId=112, NL Central divisionId=205, NL leagueId=104.
GET responses are cached in memory with a short TTL so per-tick calls on the
Pi Zero W stay cheap. Network/parse failures degrade to empty/None (logged),
never raising into the display loop.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://statsapi.mlb.com/api/v1"
CUBS_TEAM_ID = 112
NL_CENTRAL_DIVISION_ID = 205
NL_LEAGUE_ID = 104
SEASON = 2026

CENTRAL = ZoneInfo("America/Chicago")

_REQUEST_TIMEOUT = 10  # seconds
_CACHE_TTL = 300  # seconds; standings/schedule barely move within this window

# url -> (fetched_at, json)
_cache: dict[str, tuple[float, dict]] = {}


def _get(path: str, params: dict[str, str | int] | None = None, *, ttl: int = _CACHE_TTL) -> dict:
    """Cached GET against the Stats API. Returns ``{}`` on any failure."""
    query = "&".join(f"{k}={v}" for k, v in (params or {}).items())
    url = f"{BASE_URL}/{path}" + (f"?{query}" if query else "")
    cached = _cache.get(url)
    if cached and (time.monotonic() - cached[0]) < ttl:
        return cached[1]
    try:
        resp = requests.get(url, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("MLB API GET failed (%s): %s", url, exc)
        return {}
    _cache[url] = (time.monotonic(), data)
    return data


@dataclass(frozen=True)
class TeamStanding:
    """One team's NL Central standing."""

    rank: int
    abbrev: str
    wins: int
    losses: int
    games_back: str  # "-" for the leader, else e.g. "2.5"


@dataclass(frozen=True)
class Game:
    """A single Cubs game from the schedule."""

    game_pk: int
    start_utc: datetime
    state: str  # abstractGameState: Preview | Live | Final
    cubs_home: bool
    opponent_abbrev: str
    cubs_score: int | None
    opponent_score: int | None
    cubs_pitcher: str | None
    opponent_pitcher: str | None

    @property
    def start_ct(self) -> datetime:
        """Game start in America/Chicago (Cubs local time)."""
        return self.start_utc.astimezone(CENTRAL)

    @property
    def is_final(self) -> bool:
        return self.state == "Final"

    @property
    def cubs_won(self) -> bool | None:
        """True/False once Final with scores, else None (game not decided)."""
        if not self.is_final or self.cubs_score is None or self.opponent_score is None:
            return None
        return self.cubs_score > self.opponent_score


def _team_abbrevs() -> dict[int, str]:
    """Map team id -> abbreviation for all MLB teams (cached via _get)."""
    data = _get("teams", {"sportId": 1, "season": SEASON})
    return {t["id"]: t.get("abbreviation", "?") for t in data.get("teams", [])}


def _parse_game(game: dict, abbrevs: dict[int, str]) -> Game | None:
    try:
        teams = game["teams"]
        home, away = teams["home"], teams["away"]
        cubs_home = home["team"]["id"] == CUBS_TEAM_ID
        cubs, opp = (home, away) if cubs_home else (away, home)
        opp_abbrev = abbrevs.get(opp["team"]["id"]) or opp["team"].get("name", "?")[:3].upper()
        return Game(
            game_pk=game["gamePk"],
            start_utc=datetime.fromisoformat(game["gameDate"].replace("Z", "+00:00")),
            state=game.get("status", {}).get("abstractGameState", "Preview"),
            cubs_home=cubs_home,
            opponent_abbrev=opp_abbrev,
            cubs_score=cubs.get("score"),
            opponent_score=opp.get("score"),
            cubs_pitcher=cubs.get("probablePitcher", {}).get("fullName"),
            opponent_pitcher=opp.get("probablePitcher", {}).get("fullName"),
        )
    except (KeyError, ValueError) as exc:
        logger.warning("could not parse game %s: %s", game.get("gamePk"), exc)
        return None


def cubs_schedule(start: date, end: date) -> list[Game]:
    """Cubs games from ``start`` to ``end`` (inclusive), with probable pitchers."""
    data = _get(
        "schedule",
        {
            "sportId": 1,
            "teamId": CUBS_TEAM_ID,
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "hydrate": "probablePitcher",
        },
        ttl=_CACHE_TTL,
    )
    abbrevs = _team_abbrevs()
    games: list[Game] = []
    for day in data.get("dates", []):
        for raw in day.get("games", []):
            parsed = _parse_game(raw, abbrevs)
            if parsed is not None:
                games.append(parsed)
    games.sort(key=lambda g: g.start_utc)
    return games


def todays_game(today: date | None = None) -> Game | None:
    """Today's Cubs game (Central date), or None if there isn't one."""
    today = today or datetime.now(CENTRAL).date()
    games = cubs_schedule(today, today)
    return games[0] if games else None


def next_game(today: date | None = None, *, days_ahead: int = 30) -> Game | None:
    """The next Cubs game that hasn't gone Final (an in-progress game counts)."""
    today = today or datetime.now(CENTRAL).date()
    for game in cubs_schedule(today, today + timedelta(days=days_ahead)):
        if not game.is_final:
            return game
    return None


def did_cubs_win_today(today: date | None = None) -> bool:
    """True only if today's Cubs game is Final and the Cubs won (drives the W flag)."""
    game = todays_game(today)
    return bool(game and game.cubs_won)


def nl_central_standings() -> list[TeamStanding]:
    """NL Central standings (rank, abbrev, W, L, GB) for all five teams."""
    data = _get(
        "standings",
        {"leagueId": NL_LEAGUE_ID, "season": SEASON, "standingsTypes": "regularSeason"},
    )
    abbrevs = _team_abbrevs()
    for record in data.get("records", []):
        if record.get("division", {}).get("id") != NL_CENTRAL_DIVISION_ID:
            continue
        standings: list[TeamStanding] = []
        for tr in record.get("teamRecords", []):
            team_id = tr.get("team", {}).get("id")
            standings.append(
                TeamStanding(
                    rank=int(tr.get("divisionRank", 0) or 0),
                    abbrev=abbrevs.get(team_id, tr.get("team", {}).get("name", "?")[:3].upper()),
                    wins=tr.get("wins", 0),
                    losses=tr.get("losses", 0),
                    games_back=tr.get("divisionGamesBack", "-"),
                )
            )
        standings.sort(key=lambda s: s.rank)
        return standings
    return []

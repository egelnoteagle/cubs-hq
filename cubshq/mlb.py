"""MLB Stats API client (statsapi.mlb.com, unauthenticated).

Provides today's Cubs game state/result, NL Central standings, and the next
game with probable pitchers. Cubs teamId=112, NL Central divisionId=205,
NL leagueId=104. Responses are cached in memory between ticks.

TODO: implement.
"""

from __future__ import annotations

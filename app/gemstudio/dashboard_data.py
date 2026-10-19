"""The facts the native dashboard shows, as plain JSON (no Qt, no pandas).

Written beside the figure data as ``dashboard.json``, so the UI process reads a small
file instead of loading the whole parsed match. Only what the match records is here:
no scores, tags or verdicts (gem presents facts, not interpretation).
"""

from __future__ import annotations

from typing import Any

HERO_PREFIX = "npc_dota_hero_"
RADIANT, DIRE = 2, 3


def _player(player: Any, hero_display: Any) -> dict[str, Any]:
    return {
        "player_id": player.player_id,
        "name": player.player_name,
        "hero": hero_display(player.hero_name) if player.hero_name else "",
        "icon": player.hero_name.removeprefix(HERO_PREFIX) if player.hero_name else "",
        "team": "radiant" if player.team == RADIANT else "dire",
        "level": player.level,
        "kills": player.kills,
        "deaths": player.deaths,
        "assists": player.assists,
        "last_hits": player.last_hits,
        "denies": player.denies,
        "net_worth": player.net_worth,
        "gpm": player.gold_per_min,
        "xpm": player.xp_per_min,
        "hero_damage": player.hero_damage,
        "tower_damage": player.tower_damage,
        "hero_healing": player.hero_healing,
        "observers": player.obs_placed,
        "sentries": player.sen_placed,
        "buybacks": player.buyback_count,
    }


def build_dashboard(match: Any) -> dict[str, Any]:
    """Collect the dashboard's facts from a parsed match.

    Args:
        match: A ``gem.ParsedMatch`` (from ``gem.parse`` or ``gem.load_json``).

    Returns:
        ``{"match": {...}, "players": [...], "advantage": {...}}``, all JSON-compatible.
        Players are listed Radiant first, each side by net worth, highest first.
    """
    from gem.constants import hero_display

    players = [_player(p, hero_display) for p in match.players if p.hero_name]
    players.sort(key=lambda p: (p["team"] != "radiant", -p["net_worth"]))
    side = {
        team: sum(p["net_worth"] for p in players if p["team"] == team)
        for team in ("radiant", "dire")
    }
    gold = [int(v) for v in match.radiant_gold_adv]
    xp = [int(v) for v in match.radiant_xp_adv]
    return {
        "match": {
            "match_id": match.match_id,
            "radiant_win": match.radiant_win,
            "radiant_score": match.radiant_score,
            "dire_score": match.dire_score,
            "radiant_team": match.radiant_team_name,
            "dire_team": match.dire_team_name,
            "duration_s": match.duration,
            "first_blood_s": match.first_blood_time,
            "net_worth": side,
            "roshan_kills": len(match.roshans),
            "towers_destroyed": len(match.towers),
            "barracks_destroyed": len(match.barracks),
            "fights": len(match.fights),
            "wards": len(match.wards),
            "observers_placed": sum(p["observers"] for p in players),
            "sentries_placed": sum(p["sentries"] for p in players),
            "buybacks": sum(p["buybacks"] for p in players),
            "parse_error": str(match.parse_error) if match.parse_error else None,
            "truncated_at_tick": match.truncated_at_tick,
        },
        "players": players,
        "advantage": {"minutes": list(range(len(gold))), "gold": gold, "xp": xp},
    }

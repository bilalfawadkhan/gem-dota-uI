import json

import gem

from gemstudio.dashboard_data import build_dashboard


def test_truncated_replay_gives_an_empty_but_valid_dashboard(fixture_dem):
    """The fixture stops at tick 2375, before heroes are picked: no players, no curve, no crash."""
    data = build_dashboard(gem.parse(fixture_dem))
    json.dumps(data)  # plain JSON, nothing to convert
    assert data["players"] == []
    assert data["advantage"] == {"minutes": [], "gold": [], "xp": []}
    assert data["match"]["truncated_at_tick"] == 2375
    assert data["match"]["parse_error"]
    assert data["match"]["net_worth"] == {"radiant": 0, "dire": 0}


def test_players_are_listed_radiant_first_then_by_net_worth():
    class P:
        def __init__(self, team, worth, hero="npc_dota_hero_axe"):
            self.team, self.net_worth, self.hero_name = team, worth, hero
            self.player_id, self.player_name = 0, "x"
            for field in [
                "level",
                "kills",
                "deaths",
                "assists",
                "last_hits",
                "denies",
                "gold_per_min",
                "xp_per_min",
                "hero_damage",
                "tower_damage",
                "hero_healing",
                "obs_placed",
                "sen_placed",
                "buyback_count",
            ]:
                setattr(self, field, 1)

    class M:
        players = [P(3, 5000), P(2, 3000), P(3, 9000), P(2, 8000), P(2, 1, hero="")]
        match_id, radiant_win, radiant_score, dire_score = 1, True, 2, 1
        radiant_team_name = dire_team_name = ""
        duration, first_blood_time = 60, 10
        roshans = towers = barracks = fights = wards = []
        radiant_gold_adv, radiant_xp_adv = [0, 5], [0, 9]
        parse_error, truncated_at_tick = None, None

    data = build_dashboard(M())
    order = [(p["team"], p["net_worth"]) for p in data["players"]]
    assert order == [("radiant", 8000), ("radiant", 3000), ("dire", 9000), ("dire", 5000)]
    assert len(data["players"]) == 4  # the player with no hero is left out
    assert data["players"][0]["icon"] == "axe"  # the icon name is the NPC name without its prefix
    assert data["match"]["net_worth"] == {"radiant": 11000, "dire": 14000}
    assert data["advantage"] == {"minutes": [0, 1], "gold": [0, 5], "xp": [0, 9]}

# Match Reports

> [!NOTE]
> The HTML report was removed in gem 0.14, with `gem.reports`,
> `python -m gem reports` and `examples/match_report.py`. Its views became
> [Recipes](../cookbook/questions.md): each one answers a question from the match's
> facts, with a figure and the code to run on your own replays.

Where each part of the report went:

| Report view | Recipe |
|---|---|
| Fights tab: maps, timelines and playback | [Where were the fights, and who got the kills?](../cookbook/fights.md) |
| Vision tab: wards and what they saw | [Where did each team ward, and what could the wards see?](../cookbook/wards.md) |
| Laning | [How did each lane go?](../cookbook/lanes.md) |
| Gold and XP advantage | [What moved the gold and XP lead?](../cookbook/lead.md) |
| Objectives and buildings | [When did each objective fall, and did teams convert their edges?](../cookbook/objectives.md) |
| Runes | [Who took each rune, and what happened while a power rune lasted?](../cookbook/runes.md) |
| Roshan tab | [Did the Roshan team win the next fight?](../cookbook/roshan-next-fight.md) |
| Farming tab | [How fast did each core farm from 10 to 20 minutes?](../cookbook/core-farm.md) |
| Smoke Operations | [How often did a smoke lead to a kill?](../cookbook/smoke-to-kill.md) |

Purchases and neutral items, buybacks, and the draft don't have a recipe yet. Until
they do, the facts behind them are `ParsedPlayer.purchase_log` and `.buybacks`, and
`ParsedMatch.neutral_item_finds` and `.draft`. The scoreboard, the kill
feed, the per-minute combat charts and the Movement tab were dropped.

To keep generating the old report, pin the last release that has it:

```bash
pip install "gem-dota<0.14"
```

# ESPN College GameDay — Home Assistant Integration

Unofficial integration that tracks ESPN's College GameDay: season-premiere countdown, host-site announcements, featured-game details (poll ranks, kickoff, TV, betting line), guest picker, end-of-show final picks, and a multi-week lookahead of announced sites. Pairs with [gameday-card](https://github.com/kristin0202/gameday-card).

> ⚠️ Uses ESPN's **undocumented** site APIs. They can change without notice. When they do, sensors go `unavailable` (never wrong) — file an issue / patch `parser.py`.

## Install (HACS 2.x)
1. Sidebar → **HACS** → ⋮ (top-right, next to search) → **Custom repositories** → add this repo URL, type **Integration**.
2. Install **ESPN College GameDay**, restart HA.
3. Settings → Devices & Services → **Add Integration** → ESPN College GameDay.
4. Flair teams default to `Washington, Michigan` — edit at setup if needed.

## Entities

| Entity | State | Key attributes |
|---|---|---|
| `sensor.gameday_next_show` | timestamp of next show (Sat 9am ET) | `phase`, `week_number`, `show_end`, `fresh_until` |
| `sensor.gameday_location` | host school or `TBA` | `week`, `venue`, `city`, `state`, `source_url`, `confidence`, `method` |
| `sensor.gameday_guest_picker` | name or `TBA` | `source_url`, `method` |
| `sensor.gameday_featured_game` | matchup or `TBA` | `home`/`away` (incl. `school`, `rank`, `color`, `alt_color`, `logo`), `kickoff`, `tv`, `spread`, `over_under`, `venue`, `city`, `state` |
| `sensor.gameday_final_picks` | `available`/`unavailable` | `picks` (name→team), `source_url`, `method` |
| `sensor.gameday_upcoming` | next future site or `TBA` | `schedule`: `[{week, school, matchup, kickoff, city, state}]` |
| `binary_sensor.gameday_new_announcement` | on ~30 min after a *parsed* announcement | — |
| `binary_sensor.gameday_flair_week` | on when a flair team hosts | `flair_team` |

Manual overrides deliberately do **not** trigger `new_announcement` — you already knew.

## How the data is sourced

**Official seeds.** Sites announced months ahead (the premiere is typically revealed in May) age out of ESPN's ~50-item news feed long before the season and can never be parsed. `official_schedule.py` seeds those weeks authoritatively — host school only; matchup, kickoff, TV, odds, ranks, and colors still come live from the scoreboard. Seeds never fire the announcement event (a May press release is not news in August), never overwrite an existing entry, and never apply to a week that has already aired. Precedence: **official seed < parsed announcement < manual override**. Update the file each spring; old seasons can stay.

**Season rollover.** The persisted schedule is tagged with ESPN's season year. When the year changes, week-scoped state is cleared — without this, week numbers restarting at 1 would leave last season's entries looking current.

**Schedule model.** Announced sites are stored per week. "Current location" is a derived view of the week containing the next show, so when a show week ends the next site is promoted automatically — no action needed.

**Poll ranks.** ESPN's scoreboard only carries a usable `curatedRank` for the week actually in play; every future week reports `99`. Ranks for lookahead weeks therefore come from the rankings endpoint, preferring **AP Top 25 → Coaches Poll**, with a real `curatedRank` always winning when present. One poll is used outright rather than merging several, so a matchup billed "#3 at #1" has both numbers off the same ballot. Once CFP rankings begin, ESPN reuses the curated slot and those take over.

**Polling.** 6 h offseason → 60 min in-season (and the final 3 pre-season weeks) → 10 min during the Sat-evening/Sunday announcement window and Saturday show mornings.

## Events
`espn_gameday_location_announced` · `espn_gameday_picker_announced` · `espn_gameday_picks_available`

The location event payload includes `week`, so automations can distinguish "this Saturday" from a lookahead announcement.

### Example: push notification on announcement
```yaml
automation:
  - alias: "GameDay location announced"
    trigger:
      - platform: event
        event_type: espn_gameday_location_announced
    action:
      - service: notify.mobile_app_YOUR_PHONE
        data:
          title: "🏈 College GameDay"
          message: >
            Week {{ trigger.event.data.week }}: GameDay is headed to
            {{ trigger.event.data.school }}!
          data:
            url: "{{ trigger.event.data.source_url }}"
```

## Override services (safety valve — parser misses happen)
```yaml
# Current/premiere week:
service: espn_gameday.set_location
data: { school: "LSU" }

# A future week:
service: espn_gameday.set_location
data: { school: "Texas", week: 2 }

service: espn_gameday.set_picker
data: { name: "Macklemore" }

service: espn_gameday.set_picks
data:
  picks:
    Rece Davis: Ohio State
    Kirk Herbstreit: Ohio State
    Desmond Howard: Texas

service: espn_gameday.clear_overrides
```
Per-week location overrides survive restarts and are dropped automatically once that week passes.

## Known limitations (accepted by design)
- Guest picker automation ≈70%: sometimes only revealed on-air/social. Falls back to `TBA` + override.
- Final picks ≈50% with 1–3 h post-show delay: depends on a recap article appearing in ESPN's news feed.
- Announcement parsing requires the article to still be in ESPN's ~50-item news feed. Sites announced months in advance are covered by `official_schedule.py` instead; anything it misses can be set with `set_location`.
- Week attribution for an announcement without an explicit "Week N" uses the earliest week in the 3-week fetch window where that school hosts; ambiguity lowers `confidence` rather than guessing.

## Tests
```bash
python3 tests/test_official_schedule.py
```
No Home Assistant install required — the suite extracts the pure functions and the seed method from source and exercises them against a stub, so every assertion runs rather than silently skipping.

## Repo conventions
Edit files **either** in the GitHub web editor **or** by bulk upload — never both on the same file. Bulk "Add files via upload" silently overwrites web edits (this repo has lost the manifest URLs to that twice).

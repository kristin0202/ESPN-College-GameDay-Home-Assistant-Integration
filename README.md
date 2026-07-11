# ESPN College GameDay — Home Assistant Integration

Unofficial integration that tracks ESPN's College GameDay: season-premiere countdown, host-site announcements, featured-game details (ranks, kickoff, TV, betting line), guest picker, and end-of-show final picks. Pairs with [`gameday-card`](../gameday-card).

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
| `sensor.gameday_location` | host school or `TBA` | `venue`, `city`, `state`, `source_url`, `confidence`, `method` |
| `sensor.gameday_guest_picker` | name or `TBA` | `source_url`, `method` |
| `sensor.gameday_featured_game` | matchup or `TBA` | `kickoff`, `tv`, `spread`, `over_under`, ranks |
| `sensor.gameday_final_picks` | `available`/`unavailable` | `picks` (name→team), `source_url` |
| `sensor.gameday_upcoming` | next future site or `TBA` | `schedule`: `[{week, school, matchup, kickoff}]` |
| `binary_sensor.gameday_new_announcement` | on for ~30 min after a change | — |
| `binary_sensor.gameday_flair_week` | on when a flair team hosts | `flair_team` |

## Events
`espn_gameday_location_announced` · `espn_gameday_picker_announced` · `espn_gameday_picks_available`

### Example: push notification on announcement
```yaml
automation:
  - alias: "GameDay location announced"
    trigger:
      - platform: event
        event_type: espn_gameday_location_announced
    action:
      - service: notify.mobile_app_YOUR_PHONE   # e.g. your Z Fold
        data:
          title: "🏈 College GameDay"
          message: "GameDay is headed to {{ trigger.event.data.school }}!"
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

## Polling behavior
6 h offseason → 60 min in-season (and final 3 pre-season weeks) → 10 min during the Sat-evening/Sunday announcement window and Saturday show mornings.

## Known limitations (accepted by design)
- Guest picker automation ≈70%: sometimes only revealed on-air/social. Falls back to `TBA` + override.
- Final picks ≈50% with 1–3 h post-show delay: depends on a recap article appearing in ESPN's news feed.
- Week 0 shows: countdown anchors to ESPN's season calendar; the announcement parser catches a Week 0 site regardless.

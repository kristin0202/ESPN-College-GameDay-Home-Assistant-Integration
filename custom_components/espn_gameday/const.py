"""Constants for the ESPN College GameDay integration."""
from datetime import timedelta

DOMAIN = "espn_gameday"
PLATFORMS = ["sensor", "binary_sensor"]

# ESPN unofficial endpoints (undocumented; may change without notice).
SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
)
NEWS_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/news"
)
RANKINGS_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/rankings"
)
# ESPN caps the news feed at 50 items server-side and ignores `offset`, so
# this cannot be raised to see further back — verified against the live API.
# Headshot sources for the guest picker. Neither needs an API key, and both
# must be called server-side: Deezer sends no access-control-allow-origin, so
# the card cannot reach it from the browser.
ESPN_SEARCH_URL = "https://site.web.api.espn.com/apis/search/v2"
DEEZER_ARTIST_URL = "https://api.deezer.com/search/artist"

NEWS_LIMIT = 50
# Story bodies cost one request each. Only GameDay/picker headlines qualify
# (parser.wants_body), and this bounds a pathological feed.
MAX_BODY_FETCHES = 4

# Poll preference when a game's own curatedRank is unset (every future week).
# ESPN reuses the "curated" slot for the CFP rankings once those start, so a
# real curatedRank always wins; these are the fallbacks, best first.
POLL_PREFERENCE = ("ap top 25", "afca coaches poll", "coaches poll")

# Show window: 9:00 AM - 12:00 PM Eastern, Saturdays during the season.
SHOW_TZ = "America/New_York"
LOCAL_TZ = "America/Chicago"
SHOW_START_HOUR_ET = 9
SHOW_END_HOUR_ET = 12

# Adaptive polling tiers.
INTERVAL_OFFSEASON = timedelta(hours=6)
INTERVAL_IN_SEASON = timedelta(minutes=60)
INTERVAL_HOT = timedelta(minutes=10)  # announcement window + show day

# Fresh-announcement window (binary_sensor.gameday_new_announcement stays on).
FRESH_WINDOW = timedelta(minutes=30)

CONF_FLAIR_TEAMS = "flair_teams"
DEFAULT_FLAIR_TEAMS = "Washington, Michigan"

# Palettes live in the card; the integration only reports WHICH flair team matched.
STORAGE_VERSION = 1
STORAGE_KEY = "espn_gameday_state"

EVENT_LOCATION = "espn_gameday_location_announced"
EVENT_PICKER = "espn_gameday_picker_announced"
EVENT_PICKS = "espn_gameday_picks_available"

ATTR_SCHOOL = "school"
ATTR_SOURCE = "source_url"

SERVICE_SET_LOCATION = "set_location"
SERVICE_SET_PICKER = "set_picker"
SERVICE_SET_PICKS = "set_picks"
SERVICE_CLEAR_OVERRIDES = "clear_overrides"

PHASE_OFFSEASON = "offseason"
PHASE_IN_SEASON = "in_season"

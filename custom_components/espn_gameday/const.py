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
NEWS_LIMIT = 50

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

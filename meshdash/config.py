import os


DEFAULT_MESH_PORT = os.environ.get(
    "MESH_DASH_MESH_PORT",
    "COM3" if os.name == "nt" else "/dev/ttyACM0",
)
# Default gateway fallback is intentionally disabled unless explicitly configured.
DEFAULT_GATEWAY_HOST = ""
DEFAULT_GATEWAY_PORT = 4403
DEFAULT_HTTP_HOST = "0.0.0.0"
DEFAULT_HTTP_PORT = 8877
DEFAULT_REFRESH_MS = 3000
DEFAULT_PACKET_LIMIT = 250
DEFAULT_RESET_TICKER_SCALE_ON_RESTART = True
DEFAULT_HISTORY_DB = "mesh_dashboard_history.sqlite3"
DEFAULT_HISTORY_MAX_ROWS = 200000
DEFAULT_HISTORY_RETENTION_DAYS = 7
DEFAULT_HISTORY_EVENT_MAX_ROWS = 200000
DEFAULT_HISTORY_EVENT_RETENTION_DAYS = 30
DEFAULT_HISTORY_ROLLUP_RETENTION_DAYS = 365
DEFAULT_NODE_HISTORY_HOURS = 72
DEFAULT_NODE_HISTORY_MAX_POINTS = 1440
DEFAULT_CHAT_MAX_BYTES = 220

# Meshyface Rooms sideband portnum (Meshtastic "private app" range is 256-511).
#
# 256 is commonly used as the generic PRIVATE_APP bucket, so we default to 257
# to reduce accidental collisions with other experiments.
DEFAULT_ROOMS_PORTNUM = 257

DEFAULT_APP_VERSION_FALLBACK = "0.1.0"
UNKNOWN_GIT_COMMIT = "nogit"

SENSITIVE_FIELD_NAMES = {
    "private_key",
    "wifi_psk",
    "password",
    "psk",
    "session_passkey",
    "admin_key",
}

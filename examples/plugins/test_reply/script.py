"""Reply to wildcard-matched test messages with link summary macros."""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Mapping

from meshdash.plugins import Script


script = Script(id="test_reply", name="Test Reply", version="1.0.0")

_DEFAULT_PATTERNS = "*test*, *ping*"
_FALLBACK_PATTERNS = ("*test*", "*ping*")
_DEFAULT_TEMPLATE = "{hops} to {nearest_city}"
_MACRO_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
_US_STATE_ABBREVIATIONS = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
}


def _clean_text(value, fallback=""):
    text = " ".join(str(value or "").split())
    return text or fallback


def _int_or_none(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0 or parsed != parsed or not parsed.is_integer():
        return None
    return int(parsed)


def _float_or_none(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return parsed


def _first_known(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _patterns_from_config(ctx):
    raw = ctx.config.get("trigger_patterns", _DEFAULT_PATTERNS)
    if not isinstance(raw, str):
        raw = _DEFAULT_PATTERNS
    patterns = []
    for line in raw.splitlines():
        if line.lstrip().startswith("#"):
            continue
        for raw_pattern in line.split(","):
            pattern = " ".join(raw_pattern.split()).casefold()
            if pattern:
                patterns.append(pattern)
    return tuple(patterns) or _FALLBACK_PATTERNS


def _message_matches(text, patterns):
    candidate = " ".join(str(text or "").split()).casefold()
    return any(fnmatch.fnmatchcase(candidate, pattern) for pattern in patterns)


def _node(ctx, node_id):
    node = ctx.mesh.get_node(node_id)
    return node if isinstance(node, Mapping) else {}


def _node_hops(message, node):
    return _first_known(
        _int_or_none(getattr(message, "hops", None)),
        _int_or_none(node.get("hops")),
        _int_or_none(node.get("hops_away")),
        _int_or_none(node.get("last_hops")),
    )


def _city_for_node(ctx, node_id):
    position = ctx.mesh.get_node_location(node_id)
    if not isinstance(position, Mapping):
        return {}
    latitude = _first_known(
        _float_or_none(position.get("latitude")),
        _float_or_none(position.get("lat")),
    )
    longitude = _first_known(
        _float_or_none(position.get("longitude")),
        _float_or_none(position.get("lon")),
    )
    if latitude is None or longitude is None:
        return {}
    city = ctx.mesh.nearest_city(latitude, longitude)
    return city if isinstance(city, Mapping) else {}


def _city_label(city):
    name = _clean_text(city.get("name") if isinstance(city, Mapping) else "")
    if not name:
        return "unknown city"
    state = _clean_text(city.get("state") if isinstance(city, Mapping) else "")
    country = _clean_text(city.get("country") if isinstance(city, Mapping) else "")
    if country == "United States of America" and state in _US_STATE_ABBREVIATIONS:
        state = _US_STATE_ABBREVIATIONS[state]
    place = state or country
    return f"{name}, {place}" if place else name


def _format_optional_number(value, suffix=""):
    number = _float_or_none(value)
    if number is None:
        return "unknown"
    rendered = str(int(number)) if number.is_integer() else f"{number:.1f}"
    return f"{rendered}{suffix}"


def _macros(ctx, pattern):
    message = ctx.message
    sender_node = _node(ctx, message.sender_id)
    local_node = _node(ctx, message.local_node_id)
    sender_city = _city_for_node(ctx, message.sender_id)
    local_city = _city_for_node(ctx, message.local_node_id)
    hops = _node_hops(message, sender_node)
    hop_count = str(hops) if hops is not None else "unknown"
    hop_word = "hop" if hops == 1 else "hops"
    sender_long = _clean_text(sender_node.get("long_name"))
    sender_short = _clean_text(sender_node.get("short_name"))
    local_long = _clean_text(local_node.get("long_name"))
    local_short = _clean_text(local_node.get("short_name"))
    return {
        "text": message.text,
        "matched": pattern,
        "sender": sender_long or sender_short or message.sender_id,
        "sender_id": message.sender_id,
        "sender_short": sender_short or message.sender_id,
        "sender_long": sender_long or sender_short or message.sender_id,
        "local": local_long or local_short or message.local_node_id,
        "local_id": message.local_node_id,
        "local_short": local_short or message.local_node_id,
        "local_long": local_long or local_short or message.local_node_id,
        "hop_count": hop_count,
        "hop_word": hop_word,
        "hops": f"{hop_count} {hop_word}",
        "nearest_city": _city_label(sender_city),
        "city": _clean_text(sender_city.get("name")) or "unknown",
        "state": _clean_text(sender_city.get("state")) or "unknown",
        "country": _clean_text(sender_city.get("country")) or "unknown",
        "distance_km": _format_optional_number(sender_city.get("distance_km"), " km"),
        "server_city": _city_label(local_city),
        "local_city": _city_label(local_city),
        "snr": _format_optional_number(getattr(message, "snr", None), " dB"),
        "rssi": _format_optional_number(getattr(message, "rssi", None), " dBm"),
        "channel": str(getattr(message, "channel_index", 0)),
    }


def _render_template(template, values):
    def replace(match):
        return str(values.get(match.group(1), match.group(0)))

    return _MACRO_RE.sub(replace, template).strip()


@script.on_message
def test_reply(ctx):
    message = ctx.message
    if message.is_direct and ctx.config.get("reply_to_direct", True) is False:
        return None
    if message.is_broadcast and ctx.config.get("reply_to_broadcast", True) is False:
        return None

    patterns = _patterns_from_config(ctx)
    matched = next(
        (pattern for pattern in patterns if _message_matches(message.text, (pattern,))),
        "",
    )
    if not matched:
        return None

    template = ctx.config.get("response_template", _DEFAULT_TEMPLATE)
    if not isinstance(template, str) or not template.strip():
        template = _DEFAULT_TEMPLATE
    reply = _render_template(template, _macros(ctx, matched))
    return ctx.reply(reply) if reply else None

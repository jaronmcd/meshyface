START_ROOM = "trailhead"

ROOMS = {
    "trailhead": {
        "name": "Trailhead",
        "desc": "Rain. A bunker door is north.",
        "exits": {"north": "foyer"},
        "item": None,
    },
    "foyer": {
        "name": "Foyer",
        "desc": "Dusty lobby. A brass key glints.",
        "exits": {"south": "trailhead", "east": "workshop", "west": "gate"},
        "item": "key",
    },
    "workshop": {
        "name": "Workshop",
        "desc": "Old radios and a storm lamp.",
        "exits": {"west": "foyer"},
        "item": "lamp",
    },
    "gate": {
        "name": "Gate",
        "desc": "A steel gate blocks the vault.",
        "exits": {"east": "foyer", "north": "vault"},
        "item": None,
    },
    "vault": {
        "name": "Vault",
        "desc": "A lockbox hums beside a beacon.",
        "exits": {"south": "gate"},
        "item": "beacon",
    },
}

"""Compatibility facade for legacy write imports.

New code should prefer domain modules (`history_store_packets`,
`history_store_chat`, `history_store_connections`), but this module is retained to
avoid import churn for existing callers.
"""

from .history_store_chat import save_chat
from .history_store_connections import save_connection_event
from .history_store_packets import save_packet
from .history_store_summary import save_summary_metrics

__all__ = [
    "save_connection_event",
    "save_packet",
    "save_chat",
    "save_summary_metrics",
]

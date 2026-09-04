"""reaper-connector: agent interaction layer for the REAPER DAW.

Ticket 1 surface: doctor (readiness) + bridge (file-drop JSON-RPC client).
"""

from reaper_connector.bridge import BridgeTimeout, bridge_dirs, send as bridge_send
from reaper_connector.doctor import default_resource_path, report as doctor_report

__all__ = [
    "BridgeTimeout",
    "bridge_dirs",
    "bridge_send",
    "default_resource_path",
    "doctor_report",
]

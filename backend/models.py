"""Verified interface metadata shared by backend modules."""
from __future__ import annotations

SENTINEL_ABS = 1.0e8
FINGERS = ("thumb", "index", "middle", "ring", "little")

ANGLE_LAYOUT = (
    ("index", "MCP flex"), ("index", "MCP abduction"),
    ("index", "PIP flex"), ("index", "DIP flex"),
    ("middle", "MCP flex"), ("middle", "MCP abduction"),
    ("middle", "PIP flex"), ("middle", "DIP flex"),
    ("ring", "MCP flex"), ("ring", "MCP abduction"),
    ("ring", "PIP flex"), ("ring", "DIP flex"),
    ("little", "MCP flex"), ("little", "MCP abduction"),
    ("little", "PIP flex"), ("little", "DIP flex"),
    ("thumb", "MCP flex"), ("thumb", "MCP abduction"),
    ("thumb", "IP flex"),
)

JOINT_NAMES = (
    "wrist",
    "thumb_cmc", "thumb_mcp", "thumb_ip", "thumb_tip",
    "index_mcp", "index_pip", "index_dip", "index_tip",
    "middle_mcp", "middle_pip", "middle_dip", "middle_tip",
    "ring_mcp", "ring_pip", "ring_dip", "ring_tip",
    "little_mcp", "little_pip", "little_dip", "little_tip",
)

# wrist -> base, then the three phalange edges for each finger.
BONE_EDGES = tuple(
    edge
    for base in (1, 5, 9, 13, 17)
    for edge in ((0, base), (base, base + 1), (base + 1, base + 2), (base + 2, base + 3))
)

HAND_INTERFACE = {
    "package": "hand_frame",
    "type": "hand_frame/msg/HandFrame",
    "topic": "/hand_frame",
    "joint_units": "degree",
    "quaternion_order": "w,x,y,z",
    "frame_id": None,
    "uncertain": [
        "pressure physical unit",
        "right-hand dedicated bone geometry",
        "which tactile hand artwork should be mirrored",
    ],
}


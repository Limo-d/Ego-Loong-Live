# ROS 2 / Hand / Tactile interface audit

This audit was completed before the main application code was written.

## Verified ROS interfaces

- RGB: `/factor_perception/rgb/image_rect/compressed`, `sensor_msgs/msg/CompressedImage`.
- Hand: `/hand_frame`, `hand_frame/msg/HandFrame`.
- Recorded reference rates: RGB 29.84 Hz; HandFrame 100.1 Hz.
- HandFrame has no `Header` and no `frame_id`. It carries separate left/right IMU and pressure stamps.

## HandFrame

Source of truth: `/home/lenovo/Ego-loong-postprocess/hand_msg_ws/src/hand_frame/msg`.
An unchanged buildable copy is included at `hand_msg_ws/src/hand_frame`.

- Per hand: 16 IMU samples, 68 pressure floats, 27 solve-state doubles.
- `solve_state[0:16]`: index/middle/ring/little; MCP flex, MCP abduction, PIP flex, DIP flex, degrees.
- `solve_state[16:19]`: thumb MCP flex, MCP abduction, IP flex, degrees.
- `solve_state[19:23]`: thumb CMC quaternion, w/x/y/z.
- `solve_state[23:27]`: absolute hand-back quaternion, w/x/y/z.
- Missing sentinel: `1e9`; absolute value at least `1e8` is invalid.

## Forward kinematics

Ported from `/home/lenovo/Retarget/retarget/hand_retarget/layout.py`, `human_fk.py`, and
`/home/lenovo/Retarget/host/hand_config.json`.

- Model frame: x toward fingertips, y dorsal, z thumb side.
- The live human display does not use Retarget's optional left-to-right robot reflection.
- Right hand currently uses the same lengths as the left hand, with physical side offsets mirrored.

## Tactile mapping

Ported from `/home/lenovo/Ego-loong-postprocess/scripts/live_tactile_68_web.py`.

- A0-A3 thumb, B0-B3 index, C0-C3 middle, D0-D3 ring, E0-E3 little, F0-F47 palm.
- F0-F47 are six rows of eight in the exact reference coordinate order.
- Both HandFrame arrays are displayed directly. No left/right mirror or index reorder is applied.
- Units are shown as raw/Delta because the message does not define a physical pressure unit.

## RGB geometry

Mock mode is 960x540. Real mode preserves the dimensions decoded from the Topic. It never crops,
never applies an ROI and never performs a geometric resize. A historical bag decoded as 960x600;
the UI reports the actual live dimensions instead of asserting a fixed size.

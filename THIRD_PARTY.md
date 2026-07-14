# Reused reference material

All reused files were copied into this new project; the source projects were not modified.

## HandFrame ROS 2 interface

Source: `/home/lenovo/Ego-loong-postprocess/hand_msg_ws/src/hand_frame`

- `hand_msg_ws/src/hand_frame`: copied unchanged so the project can build and source its own
  `hand_frame/msg/HandFrame` and `HandImuSample` interfaces.
- Generated `build/`, `install/` and `log/` directories are produced locally by colcon and are
  not copied from the reference workspace.

## Retarget

Source: `/home/lenovo/Retarget`

- `frontend/vendor/three.module.min.js`: copied unchanged from `host/web/vendor` for offline deployment.
- `frontend/vendor/OrbitControls.js`: copied unchanged; resolved with the dashboard import map.
- `config/retarget_hand_config.reference.json`: copied unchanged from `host/hand_config.json`.
- `backend/hand_pose_processor.py`: dependency-light NumPy port of the verified state27 parsing and
  human FK in `retarget/hand_retarget/layout.py` and `human_fk.py`. SciPy was removed to keep runtime
  dependencies small; the rotation order, signs, geometry and coordinate convention are preserved.
- `frontend/js/hand/`: uses the verified FK point order and bone geometry above to drive a newly
  authored procedural surface. No Retarget robot mesh and no MANO mesh/model was copied.

Three.js is distributed under the MIT License. See the upstream Three.js project for its license.

## Ego-loong-postprocess tactile viewer

Source: `/home/lenovo/Ego-loong-postprocess/scripts/live_tactile_68_web.py`

- `backend/tactile_processor.py`: ports sensor names, all 68 normalized coordinates, median baseline,
  noise gate, asymmetric EMA and auto/fixed range behavior from the serial-only reference into a
  reusable HandFrame processor.
- `frontend/assets/hand_live.png`: copied unchanged from the asset path used by the reference viewer.

Modification reason: the reference is a single-hand USB-serial/SSE application. Ego-Loong Live must
consume left and right arrays from ROS 2 HandFrame and publish them through FastAPI WebSocket.

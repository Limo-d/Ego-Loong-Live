#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

PYTHON="${PYTHON:-/usr/bin/python3}"
echo "[1/6] Python: $(${PYTHON} --version)"
if ! "${PYTHON}" -c 'import venv' 2>/dev/null; then
  echo "ERROR: python venv unavailable. Install: sudo apt install python3.12-venv" >&2
  exit 1
fi

echo "[2/6] Create .venv with ROS/system site packages"
"${PYTHON}" -m venv --system-site-packages .venv

echo "[3/6] Install minimal web dependencies"
.venv/bin/python -m pip install -r requirements.txt

echo "[4/6] Build project-local hand_frame interface"
if [[ -f /opt/ros/jazzy/setup.bash ]]; then
  set +u
  source /opt/ros/jazzy/setup.bash
  set -u
  (
    cd hand_msg_ws
    colcon build --symlink-install --cmake-clean-cache \
      --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
  )
else
  echo "WARN: /opt/ros/jazzy/setup.bash not found; skipped hand_frame build"
fi

echo "[5/6] Check ROS and custom interface"
if [[ -f /opt/ros/jazzy/setup.bash && -f "${ROOT}/hand_msg_ws/install/setup.bash" ]]; then
  set +u
  source /opt/ros/jazzy/setup.bash
  source "${ROOT}/hand_msg_ws/install/setup.bash"
  set -u
  .venv/bin/python -c 'import rclpy; from hand_frame.msg import HandFrame; print("ROS 2 + hand_frame: OK")'
else
  echo "WARN: /opt/ros/jazzy/setup.bash not found; mock mode remains usable"
fi

echo "[6/6] Check project files"
for path in config/config.yaml frontend/index.html frontend/dashboard.html frontend/js/app.js; do
  [[ -s "${path}" ]] || { echo "ERROR: missing ${path}" >&2; exit 1; }
done
echo "Install complete. Run: ./scripts/run_mock.sh"

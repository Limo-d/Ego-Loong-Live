#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set +u
source /opt/ros/jazzy/setup.bash
source "${ROOT}/hand_msg_ws/install/setup.bash"
set -u

RGB_TOPIC="${RGB_TOPIC:-/factor_perception/rgb/image_rect/compressed}"
HAND_TOPIC="${HAND_TOPIC:-/hand_frame}"
echo "ROS_DISTRO=${ROS_DISTRO:-not sourced}"
echo "ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}"
echo "RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-default}"

if ! command -v ros2 >/dev/null; then
  echo "ERROR: ros2 not found" >&2
  exit 1
fi

/usr/bin/python3 -c 'from hand_frame.msg import HandFrame; print("hand_frame/msg/HandFrame import: OK")' || true
echo
ros2 topic list -t || true

for topic in "${RGB_TOPIC}" "${HAND_TOPIC}"; do
  echo
  echo "== ${topic} =="
  ros2 topic type "${topic}" 2>/dev/null || { echo "not discovered"; continue; }
  ros2 topic info -v "${topic}" || true
  timeout 6 ros2 topic hz "${topic}" || true
done

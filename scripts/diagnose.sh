#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set +u
source /opt/ros/jazzy/setup.bash 2>/dev/null || true
source "${ROOT}/hand_msg_ws/install/setup.bash" 2>/dev/null || true
set -u

echo "== Ego-Loong Live diagnostics =="
echo "project=${ROOT}"
echo "python=$(/usr/bin/python3 --version 2>&1)"
echo "ROS_DISTRO=${ROS_DISTRO:-unset}"
echo "ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}"
echo "RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-default}"
echo "ZENOH_SESSION_CONFIG_URI=${ZENOH_SESSION_CONFIG_URI:-unset}"
echo "AMENT_PREFIX_PATH=${AMENT_PREFIX_PATH:-unset}"
echo
echo "== imports =="
"${ROOT}/.venv/bin/python" -c 'import fastapi,uvicorn,yaml,cv2,numpy,psutil,rclpy; from hand_frame.msg import HandFrame; print("all imports: OK")' 2>&1 || true
echo
echo "== ROS topics =="
timeout 10 ros2 topic list -t 2>&1 || true
echo
echo "== ports 8000 / configured override =="
ss -ltnp 2>/dev/null | grep -E ':8000|:879[0-9]' || true
echo
echo "== backend process =="
ps -ef | grep -E '[b]ackend.main|[u]vicorn' || true

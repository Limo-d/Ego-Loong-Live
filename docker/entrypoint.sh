#!/usr/bin/env bash
# ROS setup scripts reference optional variables before assigning them, so
# nounset cannot be enabled while sourcing them.
set -eo pipefail

source "/opt/ros/${ROS_DISTRO:-jazzy}/setup.bash"
source "${APP_ROOT:-/opt/ego-loong-live}/hand_msg_ws/install/setup.bash"

# Match scripts/run.sh: connect the ROS 2 session directly to the device's
# Zenoh router unless the caller supplied a complete custom session config.
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_zenoh_cpp}"
if [[ "${RMW_IMPLEMENTATION}" == "rmw_zenoh_cpp" \
      && -z "${ZENOH_SESSION_CONFIG_URI:-}" \
      && -z "${ZENOH_CONFIG_OVERRIDE:-}" ]]; then
  endpoint="${EGO_ZENOH_ROUTER_ENDPOINT:-tcp/192.168.3.13:7447}"
  export ZENOH_CONFIG_OVERRIDE="mode=\"client\";connect/endpoints=[\"${endpoint}\"]"
fi

exec "$@"

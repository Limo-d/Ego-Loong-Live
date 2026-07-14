#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
set +u
source /opt/ros/jazzy/setup.bash
HAND_WS_SETUP="${ROOT}/hand_msg_ws/install/setup.bash"
[[ -f "${HAND_WS_SETUP}" ]] || { echo "Missing ${HAND_WS_SETUP}. Run ./scripts/install.sh first." >&2; exit 1; }
source "${HAND_WS_SETUP}"
set -u

# The live device publishes through its rmw_zenoh router. Use client mode so
# traffic is relayed instead of trying the device nodes' loopback peer locators.
# Every value remains overridable for another deployment.
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_zenoh_cpp}"
if [[ "${RMW_IMPLEMENTATION}" == "rmw_zenoh_cpp" && -z "${ZENOH_SESSION_CONFIG_URI:-}" && -z "${ZENOH_CONFIG_OVERRIDE:-}" ]]; then
  ZENOH_ROUTER_ENDPOINT="${EGO_ZENOH_ROUTER_ENDPOINT:-tcp/192.168.3.13:7447}"
  export ZENOH_CONFIG_OVERRIDE="mode=\"client\";connect/endpoints=[\"${ZENOH_ROUTER_ENDPOINT}\"]"
fi

PYTHON="${ROOT}/.venv/bin/python"
[[ -x "${PYTHON}" ]] || { echo "Missing .venv. Run ./scripts/install.sh first." >&2; exit 1; }
exec "${PYTHON}" -m backend.main "$@"

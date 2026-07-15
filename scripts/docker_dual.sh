#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${EGO_LOONG_IMAGE:-ge89jar/ego-loong-live:0715}"
ROUTER_ENDPOINT="${EGO_ZENOH_ROUTER_ENDPOINT:-}"
DEVICE01_ENDPOINT="${DEVICE01_ZENOH_ROUTER_ENDPOINT:-${ROUTER_ENDPOINT:-tcp/192.168.1.110:7447}}"
DEVICE02_ENDPOINT="${DEVICE02_ZENOH_ROUTER_ENDPOINT:-${ROUTER_ENDPOINT:-tcp/192.168.1.107:7447}}"

container_name() {
  printf 'ego-loong-device%02d' "$1"
}

container_exists() {
  docker container inspect "$(container_name "$1")" >/dev/null 2>&1
}

start_device() {
  local number="$1"
  local port domain endpoint config name
  name="$(container_name "${number}")"

  if [[ "${number}" == "1" ]]; then
    port=8001
    domain=11
    endpoint="${DEVICE01_ENDPOINT}"
    config="${ROOT}/config/device01.yaml"
  else
    port=8002
    domain=12
    endpoint="${DEVICE02_ENDPOINT}"
    config="${ROOT}/config/device02.yaml"
  fi

  if container_exists "${number}"; then
    echo "${name} already exists; remove it with: $0 stop"
    return 1
  fi

  docker run -d \
    --name "${name}" \
    --restart unless-stopped \
    --network host \
    --health-cmd "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:${port}/api/health', timeout=2).read()\"" \
    --health-interval 10s \
    --health-timeout 3s \
    --health-start-period 15s \
    --health-retries 3 \
    -e "EGO_LOONG_LIVE_CONFIG=/runtime-config/device.yaml" \
    -e "EGO_LOONG_LIVE_PORT=${port}" \
    -e "EGO_ZENOH_ROUTER_ENDPOINT=${endpoint}" \
    -v "${config}:/runtime-config/device.yaml:ro" \
    "${IMAGE}"

  echo "${name}: ROS_DOMAIN_ID=${domain}, http://localhost:${port}/dashboard"
}

stop_all() {
  local number name
  for number in 1 2; do
    name="$(container_name "${number}")"
    if container_exists "${number}"; then
      docker stop "${name}"
      docker rm "${name}"
    fi
  done
}

status_all() {
  docker ps -a \
    --filter "name=ego-loong-device01" \
    --filter "name=ego-loong-device02" \
    --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
}

case "${1:-start}" in
  start)
    start_device 1
    start_device 2
    ;;
  stop)
    stop_all
    ;;
  restart)
    stop_all
    start_device 1
    start_device 2
    ;;
  status)
    status_all
    ;;
  logs)
    device="${2:-1}"
    [[ "${device}" == "1" || "${device}" == "2" ]] || { echo "device must be 1 or 2" >&2; exit 2; }
    docker logs -f "$(container_name "${device}")"
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs [1|2]}" >&2
    exit 2
    ;;
esac

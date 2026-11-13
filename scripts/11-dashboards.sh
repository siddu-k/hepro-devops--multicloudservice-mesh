#!/usr/bin/env bash
# 11-dashboards.sh -- expose the four UIs on localhost so the Windows browser
# can reach them. `istioctl dashboard` tries to launch a Linux browser, which
# does not exist in WSL; port-forwarding is the reliable route.
#
#   bash scripts/11-dashboards.sh          start
#   bash scripts/11-dashboards.sh --stop   stop
#
# Port notes:
#   * Kiali    service kiali      20001 -> 20001
#   * Grafana  service grafana    3000  -> 3000
#   * Prometheus service prometheus 9090 -> 9090
#   * Jaeger   service tracing    16686 -> 80   (the UI is served on port 80
#     of the `tracing` service; 16686 is only the in-pod listen port)
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
init

PIDDIR="${ROOT}/.pids"
mkdir -p "$PIDDIR"

stop_all() {
  for f in "$PIDDIR"/*.pid; do
    [ -f "$f" ] || continue
    kill "$(cat "$f")" 2>/dev/null || true
    rm -f "$f"
  done
  ok "port-forwards stopped"
}

if [ "${1:-}" = "--stop" ]; then
  stop_all
  exit 0
fi

start_one() {
  local name="$1" svc="$2" local_port="$3" remote_port="$4"
  local pidfile="${PIDDIR}/${name}.pid"
  if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    ok "${name} already forwarding"
    return
  fi
  rm -f "$pidfile"
  nohup kubectl -n istio-system port-forward "svc/${svc}" \
    "${local_port}:${remote_port}" --context "$CTX1" \
    >"${PIDDIR}/${name}.log" 2>&1 &
  echo $! > "$pidfile"
  ok "${name} ${local_port} -> ${svc}:${remote_port}"
}

start_one kiali      kiali      20001 20001
start_one grafana    grafana    3000  3000
start_one prometheus prometheus 9090  9090
start_one jaeger     tracing    16686 80

say "Checking each endpoint (a UI can take a few seconds to come up)"
check() {
  local name="$1" port="$2" path="$3" i code
  for i in 1 2 3 4 5 6 7 8 9 10; do
    code="$(curl -s -o /dev/null -m 5 -w '%{http_code}' "http://127.0.0.1:${port}${path}" 2>/dev/null || true)"
    case "$code" in
      200|302|303|401) ok "${name} http://localhost:${port}  (HTTP ${code})"; return 0 ;;
    esac
    sleep 2
  done
  warn "${name} did not answer on port ${port} - see ${PIDDIR}/${name}.log"
  return 1
}

check kiali      20001 /kiali/
check grafana    3000  /login
check prometheus 9090  /-/ready
check jaeger     16686 /

cat <<EOF

Open these in the Windows browser (WSL forwards localhost):

  Kiali       http://localhost:20001     Graph -> namespace "default"
  Grafana     http://localhost:3000      Dashboards -> Istio -> Istio Mesh
  Prometheus  http://localhost:9090      query: sum(rate(istio_requests_total[1m])) by (destination_service_name)
  Jaeger      http://localhost:16686     Service: productpage.default -> Find Traces

Stop them with:  bash scripts/11-dashboards.sh --stop
EOF
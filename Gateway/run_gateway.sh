#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./run_gateway.sh dry-run /path/to/processed/session
#   ./run_gateway.sh mqtt-tls /path/to/processed/session
#
# Optional env vars for mqtt-tls:
#   MQTT_HOST (default 127.0.0.1)
#   MQTT_PORT (default 8883)
#   TOPIC_ROOT (default fincadiag/la_esmeralda)
#   CA_PATH
#   CERT_PATH
#   KEY_PATH
#   TLS_MIN_VERSION (default 1.3)

MODE="${1:-}"
SESSION_DIR="${2:-}"

if [[ -z "${MODE}" || -z "${SESSION_DIR}" ]]; then
  echo "Usage: $0 {dry-run|mqtt-tls} /path/to/processed/session" >&2
  exit 1
fi

MQTT_HOST="${MQTT_HOST:-127.0.0.1}"
MQTT_PORT="${MQTT_PORT:-8883}"
TOPIC_ROOT="${TOPIC_ROOT:-fincadiag/la_esmeralda}"
TLS_MIN_VERSION="${TLS_MIN_VERSION:-1.3}"

case "${MODE}" in
  dry-run)
    echo "[gateway] mode=dry-run"
    echo "[gateway] session-dir=${SESSION_DIR}"
    python -m fincadiag.gateway.runtime \
      --session-dir "${SESSION_DIR}" \
      --topic-root "${TOPIC_ROOT}" \
      --dry-run
    ;;

  mqtt-tls)
    : "${CA_PATH:?CA_PATH is required (path to CA PEM)}"
    : "${CERT_PATH:?CERT_PATH is required (path to client cert PEM)}"
    : "${KEY_PATH:?KEY_PATH is required (path to client key PEM)}"

    echo "[gateway] mode=mqtt-tls"
    echo "[gateway] session-dir=${SESSION_DIR}"
    echo "[gateway] mqtt=${MQTT_HOST}:${MQTT_PORT}"
    echo "[gateway] topic-root=${TOPIC_ROOT}"
    echo "[gateway] tls-min=${TLS_MIN_VERSION}"

    python -m fincadiag.gateway.runtime \
      --session-dir "${SESSION_DIR}" \
      --topic-root "${TOPIC_ROOT}" \
      --mqtt-host "${MQTT_HOST}" \
      --mqtt-port "${MQTT_PORT}" \
      --tls-enabled \
      --tls-min-version "${TLS_MIN_VERSION}" \
      --ca-path "${CA_PATH}" \
      --cert-path "${CERT_PATH}" \
      --key-path "${KEY_PATH}"
    ;;

  *)
    echo "Unknown mode: ${MODE}" >&2
    echo "Usage: $0 {dry-run|mqtt-tls} /path/to/processed/session" >&2
    exit 1
    ;;
esac

#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/deploy_hotspot.sh [target] [options]

Examples:
  # Configure hotspot + captive landing page
  ./scripts/deploy_hotspot.sh \
    --target pi@raspberrypi.local \
    --ssid Meshyface \
    --password 'change-me-please'

  # Configure hotspot on a custom subnet and dashboard port
  ./scripts/deploy_hotspot.sh \
    --target pi@raspberrypi.local \
    --ap-cidr 10.77.0.1/24 \
    --landing-ip 10.77.0.1 \
    --dash-port 8877

  # Remove hotspot + captive landing config managed by this script
  ./scripts/deploy_hotspot.sh \
    --target pi@raspberrypi.local \
    --uninstall

Options:
  --target <user@host>         SSH target host.
  --iface <name>               Wi-Fi interface (default: wlan0).
  --connection-name <name>     NetworkManager AP profile name (default: MeshyfaceAP).
  --ssid <name>                Hotspot SSID (default: Meshyface).
  --password <passphrase>      WPA2 passphrase (required unless --uninstall).
  --ap-cidr <cidr>             AP interface CIDR (default: 10.42.0.1/24).
  --landing-ip <ip>            IP used in landing redirect (default: AP IP from --ap-cidr).
  --dash-port <port>           Meshyface HTTP port (default: 8877).
  --band <bg|a|6GHz>           Wi-Fi band for AP mode (default: bg).
  --channel <num|auto>         Wi-Fi channel (default: 6).
  --no-dns-catchall            Do not force all hotspot DNS names to the landing IP.
  --uninstall                  Remove hotspot profile and captive landing config.
  -h, --help                   Show this help text.

Environment overrides:
  MESH_DASH_HOTSPOT_TARGET
  MESH_DASH_HOTSPOT_IFACE
  MESH_DASH_HOTSPOT_CONNECTION
  MESH_DASH_HOTSPOT_SSID
  MESH_DASH_HOTSPOT_PASSWORD
  MESH_DASH_HOTSPOT_AP_CIDR
  MESH_DASH_HOTSPOT_LANDING_IP
  MESH_DASH_HOTSPOT_DASH_PORT
  MESH_DASH_HOTSPOT_BAND
  MESH_DASH_HOTSPOT_CHANNEL
  MESH_DASH_HOTSPOT_DNS_CATCHALL
EOF
}

require_arg() {
  local flag="$1"
  local value="${2:-}"
  if [[ -z "${value}" ]]; then
    echo "${flag} requires a value" >&2
    exit 2
  fi
}

is_integer() {
  [[ "${1:-}" =~ ^[0-9]+$ ]]
}

TARGET="${MESH_DASH_HOTSPOT_TARGET:-}"
WLAN_IFACE="${MESH_DASH_HOTSPOT_IFACE:-wlan0}"
CONNECTION_NAME="${MESH_DASH_HOTSPOT_CONNECTION:-MeshyfaceAP}"
SSID="${MESH_DASH_HOTSPOT_SSID:-Meshyface}"
PASSWORD="${MESH_DASH_HOTSPOT_PASSWORD:-}"
AP_CIDR="${MESH_DASH_HOTSPOT_AP_CIDR:-10.42.0.1/24}"
LANDING_IP="${MESH_DASH_HOTSPOT_LANDING_IP:-}"
DASH_PORT="${MESH_DASH_HOTSPOT_DASH_PORT:-8877}"
BAND="${MESH_DASH_HOTSPOT_BAND:-bg}"
CHANNEL="${MESH_DASH_HOTSPOT_CHANNEL:-6}"
DNS_CATCHALL="${MESH_DASH_HOTSPOT_DNS_CATCHALL:-1}"
UNINSTALL=0

DNSMASQ_SHARED_FILE="/etc/NetworkManager/dnsmasq-shared.d/90-meshyface-captive.conf"
NGINX_SITE_NAME="meshyface-landing"

SSH_OPTS=(-F /dev/null)
if [[ -n "${USER:-}" ]]; then
  HOTSPOT_MUX_DIR="${TMPDIR:-/tmp}/meshdash-hotspot-${USER}"
  mkdir -p "${HOTSPOT_MUX_DIR}"
  HOTSPOT_MUX_PATH="${HOTSPOT_MUX_DIR}/cm-%r@%h:%p"
  SSH_OPTS+=(-o ControlMaster=auto -o ControlPersist=5m -o ControlPath="${HOTSPOT_MUX_PATH}")
fi

ssh_cmd() {
  ssh "${SSH_OPTS[@]}" "$@"
}

ssh_tty_cmd() {
  ssh "${SSH_OPTS[@]}" -tt "$@"
}

ensure_remote_sudo_ticket() {
  echo "[hotspot] validating remote sudo access on ${TARGET}"
  ssh_tty_cmd "${TARGET}" "sudo -v"
}

POSITIONAL_TARGET_SET=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      require_arg "$1" "${2:-}"
      TARGET="$2"
      shift 2
      ;;
    --iface)
      require_arg "$1" "${2:-}"
      WLAN_IFACE="$2"
      shift 2
      ;;
    --connection-name)
      require_arg "$1" "${2:-}"
      CONNECTION_NAME="$2"
      shift 2
      ;;
    --ssid)
      require_arg "$1" "${2:-}"
      SSID="$2"
      shift 2
      ;;
    --password)
      require_arg "$1" "${2:-}"
      PASSWORD="$2"
      shift 2
      ;;
    --ap-cidr)
      require_arg "$1" "${2:-}"
      AP_CIDR="$2"
      shift 2
      ;;
    --landing-ip)
      require_arg "$1" "${2:-}"
      LANDING_IP="$2"
      shift 2
      ;;
    --dash-port)
      require_arg "$1" "${2:-}"
      DASH_PORT="$2"
      shift 2
      ;;
    --band)
      require_arg "$1" "${2:-}"
      BAND="$2"
      shift 2
      ;;
    --channel)
      require_arg "$1" "${2:-}"
      CHANNEL="$2"
      shift 2
      ;;
    --no-dns-catchall)
      DNS_CATCHALL=0
      shift
      ;;
    --uninstall)
      UNINSTALL=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [[ "${POSITIONAL_TARGET_SET}" -eq 0 ]]; then
        TARGET="$1"
        POSITIONAL_TARGET_SET=1
        shift
      else
        echo "unexpected argument: $1" >&2
        usage >&2
        exit 2
      fi
      ;;
  esac
done

if [[ $# -gt 0 ]]; then
  echo "unexpected trailing arguments: $*" >&2
  usage >&2
  exit 2
fi

if [[ -z "${TARGET}" ]]; then
  cat >&2 <<'EOF'
No hotspot target supplied.

Examples:
  ./scripts/deploy_hotspot.sh --target pi@raspberrypi.local
  ./scripts/deploy_hotspot.sh --target pi@raspberrypi.local --ssid Meshyface --password 'change-me-please'

You can also set MESH_DASH_HOTSPOT_TARGET in your environment.
EOF
  exit 2
fi

if [[ -z "${LANDING_IP}" ]]; then
  LANDING_IP="${AP_CIDR%%/*}"
fi

if ! is_integer "${DASH_PORT}"; then
  echo "--dash-port must be an integer" >&2
  exit 2
fi
if (( DASH_PORT < 1 || DASH_PORT > 65535 )); then
  echo "--dash-port must be in range 1-65535" >&2
  exit 2
fi

if [[ "${BAND}" != "bg" && "${BAND}" != "a" && "${BAND}" != "6GHz" ]]; then
  echo "--band must be one of: bg, a, 6GHz" >&2
  exit 2
fi

if [[ "${CHANNEL}" != "auto" ]] && ! is_integer "${CHANNEL}"; then
  echo "--channel must be an integer or 'auto'" >&2
  exit 2
fi

if [[ "${DNS_CATCHALL}" != "0" && "${DNS_CATCHALL}" != "1" ]]; then
  echo "MESH_DASH_HOTSPOT_DNS_CATCHALL must be 0 or 1" >&2
  exit 2
fi

if [[ "${UNINSTALL}" -eq 0 ]]; then
  if [[ -z "${PASSWORD}" ]]; then
    echo "Set MESH_DASH_HOTSPOT_PASSWORD or pass --password before deploying." >&2
    exit 2
  fi
  if [[ "${#PASSWORD}" -lt 8 ]]; then
    echo "hotspot password must be at least 8 characters for WPA-PSK" >&2
    exit 2
  fi
fi

echo "[hotspot] target=${TARGET}"
echo "[hotspot] iface=${WLAN_IFACE} connection=${CONNECTION_NAME} ssid=${SSID}"
echo "[hotspot] ap_cidr=${AP_CIDR} landing_ip=${LANDING_IP} dash_port=${DASH_PORT}"
echo "[hotspot] band=${BAND} channel=${CHANNEL} dns_catchall=${DNS_CATCHALL} uninstall=${UNINSTALL}"

if [[ "${UNINSTALL}" -eq 1 ]]; then
  ensure_remote_sudo_ticket
  ssh_cmd "${TARGET}" "bash -s -- '${WLAN_IFACE}' '${CONNECTION_NAME}' '${DNSMASQ_SHARED_FILE}' '${NGINX_SITE_NAME}'" <<'REMOTE'
set -euo pipefail
WLAN_IFACE="$1"
CONNECTION_NAME="$2"
DNSMASQ_SHARED_FILE="$3"
NGINX_SITE_NAME="$4"

sudo -n true

if command -v nmcli >/dev/null 2>&1; then
  sudo -n nmcli connection down "${CONNECTION_NAME}" >/dev/null 2>&1 || true
  sudo -n nmcli connection delete "${CONNECTION_NAME}" >/dev/null 2>&1 || true
  sudo -n nmcli radio wifi on || true
fi

sudo -n rm -f "${DNSMASQ_SHARED_FILE}"
sudo -n rm -f "/etc/nginx/sites-enabled/${NGINX_SITE_NAME}"
sudo -n rm -f "/etc/nginx/sites-available/${NGINX_SITE_NAME}"

if command -v nginx >/dev/null 2>&1 || [[ -x /usr/sbin/nginx ]]; then
  sudo -n nginx -t >/dev/null 2>&1 && sudo -n systemctl reload nginx || true
fi

echo "[hotspot] uninstall complete"
REMOTE

  exit 0
fi

ensure_remote_sudo_ticket
ssh_cmd "${TARGET}" "bash -s -- '${WLAN_IFACE}' '${CONNECTION_NAME}' '${SSID}' '${PASSWORD}' '${AP_CIDR}' '${LANDING_IP}' '${DASH_PORT}' '${BAND}' '${CHANNEL}' '${DNS_CATCHALL}' '${DNSMASQ_SHARED_FILE}' '${NGINX_SITE_NAME}'" <<'REMOTE'
set -euo pipefail
WLAN_IFACE="$1"
CONNECTION_NAME="$2"
SSID="$3"
PASSWORD="$4"
AP_CIDR="$5"
LANDING_IP="$6"
DASH_PORT="$7"
BAND="$8"
CHANNEL="$9"
DNS_CATCHALL="${10}"
DNSMASQ_SHARED_FILE="${11}"
NGINX_SITE_NAME="${12}"

sudo -n true

if ! command -v nmcli >/dev/null 2>&1; then
  echo "nmcli not found on target; install NetworkManager first." >&2
  exit 1
fi

if ! nmcli -t -f DEVICE device status | grep -Fxq "${WLAN_IFACE}"; then
  echo "wifi interface '${WLAN_IFACE}' not found on target." >&2
  nmcli device status >&2
  exit 1
fi

sudo -n nmcli radio wifi on

if nmcli -t -f NAME connection show | grep -Fxq "${CONNECTION_NAME}"; then
  sudo -n nmcli connection modify "${CONNECTION_NAME}" connection.interface-name "${WLAN_IFACE}" 802-11-wireless.ssid "${SSID}"
else
  sudo -n nmcli connection add type wifi ifname "${WLAN_IFACE}" con-name "${CONNECTION_NAME}" autoconnect yes ssid "${SSID}"
fi

sudo -n nmcli connection modify "${CONNECTION_NAME}" \
  connection.autoconnect yes \
  802-11-wireless.mode ap \
  802-11-wireless.band "${BAND}" \
  ipv4.method shared \
  ipv4.addresses "${AP_CIDR}" \
  ipv6.method disabled \
  802-11-wireless-security.key-mgmt wpa-psk \
  802-11-wireless-security.psk "${PASSWORD}"

if [[ "${CHANNEL}" == "auto" ]]; then
  sudo -n nmcli connection modify "${CONNECTION_NAME}" 802-11-wireless.channel 0
else
  sudo -n nmcli connection modify "${CONNECTION_NAME}" 802-11-wireless.channel "${CHANNEL}"
fi

if [[ "${DNS_CATCHALL}" == "1" ]]; then
  printf 'address=/#/%s\n' "${LANDING_IP}" | sudo -n tee "${DNSMASQ_SHARED_FILE}" >/dev/null
else
  sudo -n rm -f "${DNSMASQ_SHARED_FILE}"
fi

if ! command -v nginx >/dev/null 2>&1 && [[ ! -x /usr/sbin/nginx ]]; then
  sudo -n apt-get update
  sudo -n apt-get install -y nginx
fi

sudo -n tee "/etc/nginx/sites-available/${NGINX_SITE_NAME}" >/dev/null <<EOF_NGINX
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    location = /generate_204 { return 302 http://${LANDING_IP}:${DASH_PORT}/; }
    location = /hotspot-detect.html { return 302 http://${LANDING_IP}:${DASH_PORT}/; }
    location = /ncsi.txt { return 302 http://${LANDING_IP}:${DASH_PORT}/; }
    location = /connecttest.txt { return 302 http://${LANDING_IP}:${DASH_PORT}/; }
    location / { return 302 http://${LANDING_IP}:${DASH_PORT}/; }
}
EOF_NGINX

sudo -n rm -f /etc/nginx/sites-enabled/default
sudo -n ln -sfn "/etc/nginx/sites-available/${NGINX_SITE_NAME}" "/etc/nginx/sites-enabled/${NGINX_SITE_NAME}"
sudo -n nginx -t
sudo -n systemctl enable --now nginx
sudo -n systemctl reload nginx

sudo -n nmcli connection down "${CONNECTION_NAME}" >/dev/null 2>&1 || true
sudo -n nmcli connection up "${CONNECTION_NAME}"

echo "[hotspot] active connections:"
nmcli -f NAME,TYPE,DEVICE connection show --active
echo "[hotspot] interface:"
ip -br a show "${WLAN_IFACE}" || true
echo "[hotspot] landing probe:"
curl --noproxy '*' -sSI "http://${LANDING_IP}/" | sed -n '1,5p'
REMOTE

target_host="${TARGET#*@}"
echo "[hotspot] complete"
echo "[hotspot] connect clients to SSID '${SSID}' and open: http://${LANDING_IP}:${DASH_PORT}"
echo "[hotspot] LAN access (if reachable): http://${target_host}:${DASH_PORT}"

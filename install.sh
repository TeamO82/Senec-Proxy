#!/usr/bin/env bash
set -Eeuo pipefail

REPOSITORY="TeamO82/Senec-Proxy"
VERSION="${SENEC_PROXY_VERSION:-main}"
INSTALL_DIR="/usr/local/senec-proxy"
SERVICE_FILE="/etc/systemd/system/senec-proxy.service"
SERVICE_USER="senec-proxy"

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

if [[ "$(uname -s)" != "Linux" ]]; then
    fail "This installer supports Linux systems only."
fi

if [[ "${EUID}" -ne 0 ]]; then
    fail "Run this installer as root, for example: sudo bash install.sh"
fi

command -v systemctl >/dev/null 2>&1 || fail "systemd/systemctl is required."
command -v python3 >/dev/null 2>&1 || fail "Python 3 is required. Install it before running this installer."
[[ "$VERSION" =~ ^[A-Za-z0-9._-]+$ ]] || fail "SENEC_PROXY_VERSION may contain only letters, numbers, dots, underscores, and hyphens."

if command -v curl >/dev/null 2>&1; then
    fetch() { curl --fail --silent --show-error --location "$1" --output "$2"; }
elif command -v wget >/dev/null 2>&1; then
    fetch() { wget --quiet --output-document="$2" "$1"; }
else
    fail "Install curl or wget before running this installer."
fi

if [[ -z "${SENEC_HOST:-}" ]]; then
    if [[ ! -t 0 ]]; then
        fail "Set SENEC_HOST to your SENEC hostname or IPv4 address when running non-interactively."
    fi
    read -r -p "SENEC hostname or IPv4 address: " SENEC_HOST
fi

[[ -n "$SENEC_HOST" ]] || fail "A SENEC hostname or IPv4 address is required."
[[ "$SENEC_HOST" =~ ^[A-Za-z0-9.-]+$ ]] || fail "Invalid SENEC hostname or IPv4 address: $SENEC_HOST"

SENEC_PORT="${SENEC_PORT:-443}"
[[ "$SENEC_PORT" =~ ^[0-9]+$ ]] || fail "SENEC_PORT must be a number between 1 and 65535."
(( ${#SENEC_PORT} <= 5 )) || fail "SENEC_PORT must be between 1 and 65535."
SENEC_PORT=$((10#$SENEC_PORT))
(( SENEC_PORT >= 1 && SENEC_PORT <= 65535 )) || fail "SENEC_PORT must be between 1 and 65535."

TEMP_DIR="$(mktemp -d)"
cleanup() { rm -rf "$TEMP_DIR"; }
trap cleanup EXIT

RAW_BASE="https://raw.githubusercontent.com/${REPOSITORY}/${VERSION}"
fetch "${RAW_BASE}/senec-proxy.py" "$TEMP_DIR/senec-proxy.py" || fail "Could not download senec-proxy.py from GitHub."
fetch "${RAW_BASE}/senec-proxy.conf.example" "$TEMP_DIR/senec-proxy.conf.example" || fail "Could not download the example configuration from GitHub."

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --user-group --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin "$SERVICE_USER"
fi

install -d -o root -g "$SERVICE_USER" -m 0750 "$INSTALL_DIR"
install -o root -g root -m 0755 "$TEMP_DIR/senec-proxy.py" "$INSTALL_DIR/senec-proxy.py"

CONFIG_FILE="$INSTALL_DIR/senec-proxy.conf"
if [[ ! -e "$CONFIG_FILE" ]]; then
    sed -e "s/^host = .*/host = ${SENEC_HOST}/" \
        -e "s/^port = .*/port = ${SENEC_PORT}/" \
        "$TEMP_DIR/senec-proxy.conf.example" > "$TEMP_DIR/senec-proxy.conf"
    install -o root -g "$SERVICE_USER" -m 0640 "$TEMP_DIR/senec-proxy.conf" "$CONFIG_FILE"
else
    printf 'Keeping existing configuration at %s\n' "$CONFIG_FILE"
    chown root:"$SERVICE_USER" "$CONFIG_FILE"
    chmod 0640 "$CONFIG_FILE"
fi

touch "$INSTALL_DIR/senec-proxy.log"
chown root:"$SERVICE_USER" "$INSTALL_DIR/senec-proxy.log"
chmod 0660 "$INSTALL_DIR/senec-proxy.log"

cat > "$SERVICE_FILE" <<'UNIT'
[Unit]
Description=SENEC lala.cgi cache proxy
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=senec-proxy
Group=senec-proxy
WorkingDirectory=/usr/local/senec-proxy
ExecStart=/usr/bin/python3 /usr/local/senec-proxy/senec-proxy.py
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/usr/local/senec-proxy/senec-proxy.log
UMask=0027

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
if systemctl is-active --quiet senec-proxy.service; then
    systemctl restart senec-proxy.service
else
    systemctl enable --now senec-proxy.service
fi

printf '\nSenec-Proxy is installed and enabled.\n'
printf 'Configuration: %s\n' "$CONFIG_FILE"
printf 'Check status:  systemctl status senec-proxy.service\n'
printf 'View logs:     journalctl -u senec-proxy.service -n 50 --no-pager\n'
printf 'Proxy status:  curl http://127.0.0.1:8765/status\n'


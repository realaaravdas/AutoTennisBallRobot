#!/usr/bin/env bash
# Run once on the Raspberry Pi 3B+ to configure it as a WiFi access point.
# The Pi will broadcast "TennisBotAP" and always be reachable at 10.0.0.1.
# After running this, reboot the Pi and connect your laptop to TennisBotAP.
#
# Usage: sudo bash setup_hotspot.sh [ssid] [password]
#   ssid     - network name (default: TennisBotAP)
#   password - WPA2 password, min 8 chars (default: tennisbot)

set -e

SSID="${1:-TennisBotAP}"
PASS="${2:-tennisbot}"
AP_IP="10.0.0.1"
DHCP_RANGE_START="10.0.0.2"
DHCP_RANGE_END="10.0.0.20"

if [ "$EUID" -ne 0 ]; then
    echo "Run with sudo: sudo bash setup_hotspot.sh"
    exit 1
fi

echo "=== Installing hostapd and dnsmasq ==="
apt-get update -qq
apt-get install -y hostapd dnsmasq

systemctl stop hostapd dnsmasq 2>/dev/null || true
systemctl unmask hostapd

echo "=== Configuring static IP for wlan0 ==="
DHCPCD=/etc/dhcpcd.conf
# Remove any existing wlan0 static block written by this script
sed -i '/# tennis-hotspot-begin/,/# tennis-hotspot-end/d' "$DHCPCD"
cat >> "$DHCPCD" <<EOF

# tennis-hotspot-begin
interface wlan0
    static ip_address=${AP_IP}/24
    nohook wpa_supplicant
# tennis-hotspot-end
EOF

echo "=== Configuring dnsmasq (DHCP for clients) ==="
cat > /etc/dnsmasq.conf <<EOF
interface=wlan0
dhcp-range=${DHCP_RANGE_START},${DHCP_RANGE_END},255.255.255.0,24h
EOF

echo "=== Configuring hostapd (access point) ==="
cat > /etc/hostapd/hostapd.conf <<EOF
interface=wlan0
driver=nl80211
ssid=${SSID}
hw_mode=g
channel=6
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=${PASS}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

# Point hostapd at the config
sed -i 's|^#\?DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd

echo "=== Enabling services ==="
systemctl enable hostapd dnsmasq

echo ""
echo "Done! Settings:"
echo "  SSID     : ${SSID}"
echo "  Password : ${PASS}"
echo "  Robot IP : ${AP_IP}"
echo ""
echo "Reboot the Pi now: sudo reboot"
echo "Then connect your laptop to '${SSID}' and run:"
echo "  python3 controller.py  (defaults to ${AP_IP})"

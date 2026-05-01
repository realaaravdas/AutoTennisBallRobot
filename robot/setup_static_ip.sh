#!/usr/bin/env bash
# Run once on the Raspberry Pi 3B+ to assign it a static IP on an existing LAN.
# The Pi connects to a router as a normal WiFi client — no hotspot is created.
#
# Usage: sudo bash setup_static_ip.sh <static_ip> <router_ip> [interface]
#   static_ip  - IP to assign the Pi (e.g. 192.168.1.50)
#   router_ip  - your router/gateway IP (e.g. 192.168.1.1)
#   interface  - network interface (default: wlan0)
#
# WiFi credentials must already be configured in /etc/wpa_supplicant/wpa_supplicant.conf.
# To add a network interactively:
#   sudo raspi-config  →  System Options → Wireless LAN
# Or manually:
#   wpa_passphrase "YourSSID" "YourPassword" | sudo tee -a /etc/wpa_supplicant/wpa_supplicant.conf

set -e

STATIC_IP="${1:?Usage: sudo bash setup_static_ip.sh <static_ip> <router_ip> [interface]}"
ROUTER_IP="${2:?Usage: sudo bash setup_static_ip.sh <static_ip> <router_ip> [interface]}"
IFACE="${3:-wlan0}"

if [ "$EUID" -ne 0 ]; then
    echo "Run with sudo: sudo bash setup_static_ip.sh"
    exit 1
fi

# Derive subnet mask prefix from a /24 assumption; adjust if your LAN differs.
PREFIX="24"

echo "=== Disabling access-point services (if present) ==="
for svc in hostapd dnsmasq; do
    if systemctl is-enabled "$svc" &>/dev/null; then
        systemctl disable --now "$svc" 2>/dev/null || true
        echo "  disabled $svc"
    fi
done

echo "=== Writing static IP to /etc/dhcpcd.conf ==="
DHCPCD=/etc/dhcpcd.conf

# Remove any block previously written by setup_hotspot.sh or this script.
sed -i '/# tennis-hotspot-begin/,/# tennis-hotspot-end/d' "$DHCPCD"
sed -i '/# tennis-static-begin/,/# tennis-static-end/d' "$DHCPCD"

cat >> "$DHCPCD" <<EOF

# tennis-static-begin
interface ${IFACE}
    static ip_address=${STATIC_IP}/${PREFIX}
    static routers=${ROUTER_IP}
    static domain_name_servers=${ROUTER_IP} 8.8.8.8
# tennis-static-end
EOF

echo ""
echo "Done! Settings:"
echo "  Interface : ${IFACE}"
echo "  Static IP : ${STATIC_IP}/${PREFIX}"
echo "  Gateway   : ${ROUTER_IP}"
echo ""
echo "Reboot the Pi now: sudo reboot"
echo "Then run the controller with:"
echo "  python3 controller/controller.py ${STATIC_IP}"

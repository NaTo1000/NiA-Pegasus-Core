#!/usr/bin/env bash
# MANAGED SWITCH ACCESS & CONFIGURATION TOOLKIT (Linux container version)
set -euo pipefail

banner() {
  echo "🌐 MANAGED SWITCH ACCESS TOOLKIT 🌐"
}

require_cmd() {
  local cmd="$1" hint="${2:-}"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "❌ Missing dependency: $cmd" >&2
    [ -n "$hint" ] && echo "   $hint" >&2
    return 1
  fi
}

# Auto-detect local subnet inside container (best-effort)
get_default_subnet() {
  # Try ip route then fallback to ifconfig
  if command -v ip >/dev/null 2>&1; then
    local ipaddr
    ipaddr=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}' | head -n1)
    if [ -n "${ipaddr:-}" ]; then
      echo "${ipaddr%.*}.0/24"
      return 0
    fi
  fi
  if command -v ifconfig >/dev/null 2>&1; then
    local ipaddr
    ipaddr=$(ifconfig | awk '/inet / && $2 != "127.0.0.1" {print $2; exit}')
    if [ -n "${ipaddr:-}" ]; then
      echo "${ipaddr%.*}.0/24"
      return 0
    fi
  fi
  echo "192.168.1.0/24"
}

discover_switches() {
  banner
  require_cmd nmap "Install nmap in the image." || return 1
  local subnet="${1:-}"
  if [ -z "$subnet" ]; then
    subnet=$(get_default_subnet)
  fi
  echo "🔍 Scanning subnet: $subnet"
  echo "— TCP management ports (22,23,80,443,8080,8443)"
  nmap -Pn -sS -sV --open -p 22,23,80,443,8080,8443 "$subnet"
  echo
  echo "— SNMP UDP 161 (info script)"
  if nmap --version >/dev/null 2>&1; then
    nmap -Pn -sU -p 161 --script snmp-info --open "$subnet" || true
  fi
  echo "✅ Discovery complete"
}

try_web_interface() {
  local ip="$1"
  require_cmd curl || return 1
  for port in 80 443 8080 8443; do
    echo "Checking http://$ip:$port"
    if curl -fsS --max-time 5 "http://$ip:$port" | grep -qiE "switch|management|login"; then
      echo "✅ Web interface likely at http://$ip:$port"
    fi
    echo "Checking https://$ip:$port"
    if curl -kfsS --max-time 5 "https://$ip:$port" | grep -qiE "switch|management|login"; then
      echo "✅ HTTPS interface likely at https://$ip:$port"
    fi
  done
}

try_cli_access() {
  local ip="$1"
  require_cmd nc || return 1
  if nc -z -w3 "$ip" 22 2>/dev/null; then
    echo "✅ SSH open on $ip:22 (try: ssh admin@$ip)"
  fi
  if nc -z -w3 "$ip" 23 2>/dev/null; then
    echo "✅ Telnet open on $ip:23 (warning: unencrypted)"
  fi
}

try_snmp_access() {
  local ip="$1"
  if ! command -v snmpget >/dev/null 2>&1; then
    echo "ℹ️  net-snmp not installed in image; skipping SNMP checks"
    return 0
  fi
  for community in public private admin manager cisco default; do
    echo "Trying SNMP community: $community"
    if snmpget -v2c -c "$community" -t 1 -r 0 "$ip" 1.3.6.1.2.1.1.1.0 >/dev/null 2>&1; then
      echo "✅ SNMP responds with community '$community'"
      snmpget -v2c -c "$community" "$ip" 1.3.6.1.2.1.1.1.0 || true
      break
    fi
  done
}

try_default_creds() {
  cat <<'TXT'
🔑 Common default credentials (change immediately):
- Cisco: admin/admin, cisco/cisco, admin/cisco, admin/(blank)
- Netgear: admin/password, admin/1234, admin/(blank)
- HP/Aruba: admin/admin, manager/manager, admin/(blank)
- Dell: admin/admin, root/calvin, admin/password
- D-Link: admin/(blank), admin/admin, Admin/Admin
- TP-Link: admin/admin, admin/1234
TXT
}

detailed_port_scan() {
  local ip="$1"
  require_cmd nmap || return 1
  echo "🔍 Detailed port scan for $ip"
  nmap -Pn -sS -sV -p 21,22,23,53,80,161,162,443,514,8080,8443,9000-9010 "$ip"
}

security_assessment() {
  local ip="$1"
  echo "🛡️  Security assessment for $ip"
  if command -v nc >/dev/null 2>&1; then
    nc -z -w3 "$ip" 23 2>/dev/null && echo "⚠️  Telnet enabled" || true
    nc -z -w3 "$ip" 21 2>/dev/null && echo "⚠️  FTP enabled" || true
  fi
  if command -v snmpget >/dev/null 2>&1; then
    if snmpget -v1 -c public -t 1 -r 0 "$ip" 1.3.6.1.2.1.1.1.0 >/dev/null 2>&1; then
      echo "⚠️  SNMP with default community 'public'"
    fi
  fi
  if command -v curl >/dev/null 2>&1; then
    curl -kfsS --max-time 5 "https://$ip" >/dev/null 2>&1 || true
  fi
  cat <<'TXT'
Recommendations:
1. Disable Telnet; use SSH only
2. Change default SNMP communities
3. Use strong admin passwords
4. Enable HTTPS with valid certificates
5. Restrict management access by IP
6. Enable logging and monitoring
TXT
}

vlan_config_helper() {
  cat <<'TXT'
🌐 VLAN Configuration Helper
Suggested VLANs:
- VLAN 10: Management (192.168.10.0/24)
- VLAN 20: Servers (192.168.20.0/24)
- VLAN 30: Workstations (192.168.30.0/24)
- VLAN 99: Quarantine (192.168.99.0/24)

Cisco sample:
vlan 10
 name Management
exit
interface vlan 10
 ip address 192.168.10.1 255.255.255.0
exit
interface gi1/1
 switchport mode trunk
 switchport trunk allowed vlan 10,20,30
exit
TXT
}

usage() {
  cat <<'TXT'
Usage:
  switch_toolkit.sh                # interactive menu
  switch_toolkit.sh discover [CIDR]
  switch_toolkit.sh access <IP>
  switch_toolkit.sh security <IP>
  switch_toolkit.sh vlan
TXT
}

main_menu() {
  banner
  echo "1) Discover switches on network"
  echo "2) Access specific switch"
  echo "3) Security assessment"
  echo "4) VLAN configuration helper"
  echo "5) Exit"
  printf "Select option [1-5]: "
  read -r choice
  case "$choice" in
    1)
      discover_switches
      ;;
    2)
      printf "Enter switch IP address: "
      read -r ip
      try_web_interface "$ip"
      try_cli_access "$ip"
      try_snmp_access "$ip"
      try_default_creds
      detailed_port_scan "$ip"
      ;;
    3)
      printf "Enter switch IP address: "
      read -r ip
      security_assessment "$ip"
      ;;
    4)
      vlan_config_helper
      ;;
    5)
      exit 0
      ;;
    *)
      echo "Invalid option"
      ;;
  esac
}

# Entry point
case "${1:-interactive}" in
  interactive)
    main_menu
    ;;
  discover)
    shift || true
    discover_switches "${1:-}"
    ;;
  access)
    shift || true
    [ -z "${1:-}" ] && { usage; exit 1; }
    try_web_interface "$1"
    try_cli_access "$1"
    try_snmp_access "$1"
    try_default_creds
    detailed_port_scan "$1"
    ;;
  security)
    shift || true
    [ -z "${1:-}" ] && { usage; exit 1; }
    security_assessment "$1"
    ;;
  vlan)
    vlan_config_helper
    ;;
  *)
    usage
    exit 1
    ;;
esac

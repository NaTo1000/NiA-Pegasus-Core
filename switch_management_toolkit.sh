#!/bin/bash
# MANAGED SWITCH ACCESS & CONFIGURATION TOOLKIT
# For enterprise network management and security hardening

echo "🌐 MANAGED SWITCH ACCESS TOOLKIT 🌐"

# Function to check for a command and suggest installation if missing
check_command() {
    local cmd=$1
    local package=${2:-$1}
    if ! command -v "$cmd" &> /dev/null; then
        echo "⚠️  Warning: command '$cmd' not found."
        echo "   Please install it to ensure all script functions work correctly."
        echo "   On macOS with Homebrew, you can try: brew install $package"
    fi
}

# Auto-discover switches on network
discover_switches() {
    echo "🔍 Scanning for managed switches on network..."
    
    # Get local subnet for macOS
    local_ip=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | cut -d' ' -f2 | head -n1)
    if [ -z "$local_ip" ]; then
        echo "❌ Could not determine local IP address."
        return 1
    fi
    subnet=$(echo $local_ip | cut -d'.' -f1-3).0/24
    
    echo "Scanning subnet: $subnet"
    
    # Common switch management ports
    mgmt_ports=(80 443 22 23 161 8080 8443)
    
    # Scan for devices with management interfaces
    for port in "${mgmt_ports[@]}"; do
        echo "Scanning for port $port..."
        nmap -p $port --open $subnet | grep -E "^Nmap scan report|$port/tcp open"
    done
    
    # SNMP discovery
    echo ""
    echo "🔍 SNMP discovery (community: public)..."
    nmap -sU -p 161 --script snmp-info $subnet | grep -A5 "Host is up"
}

# Common switch access methods
try_web_interface() {
    local ip=$1
    echo "🌐 Trying web interface access for $ip..."
    
    # Common web ports for switches
    web_ports=(80 443 8080 8443)
    
    for port in "${web_ports[@]}"; do
        echo "Checking http://$ip:$port"
        if curl -s --connect-timeout 5 http://$ip:$port | grep -qi "switch\|management\|login"; then
            echo "✅ Web interface found at http://$ip:$port"
                               to identify switch model
            response=$(curl -s http://$ip:$port)
            if echo "$response" | grep -qi "cisco"; then
                echo "    ppears to be Cisco device"
            elif echo "$response" | grep -qi "netgear"; then
                echo "   Appears to be Netgea                echo "   Appears to be Netgea                echo "   Appears to         echo "                 ec/Aruba device"
            elif echo "$response" | grep -qi "dell"; then
                echo "   Appears to be Dell device"
            fi
        fi
        
        # Try HTTPS
        echo "Checking https://$ip:$port"
        if curl -k -s --connect-timeout 5 https://$ip:$port | grep -qi "switch\|management\|login"; then
            echo "✅ HTTPS interface found at https://$ip:$port"
        fi
    done
}

# SSH/Telnet access attempts
try_cli_access() {
    local ip=$1
    echo "💻 Trying CLI access for $ip..."
    
    # Check SSH
    if nc -z -w5 $ip 22 2>/dev/null; then
        echo "✅ SSH port open on $ip:22"
        echo "Try: ssh admin@$ip"
        
        # Common SSH usernames for switches
        echo "Common usernames: a        echo "Common usernames: a        echo "Comm  # Check Telnet
    if nc -z -w5 $ip 23 2>/dev/null; then
        echo "✅ Telnet port open on $ip:23"
        echo "Try: telnet $ip"
        echo "⚠️  Warning: Telnet is unencrypted!"
    fi
}

# SNMP access
try_snmp_access() {
    local ip=$1
    echo "📡 Trying SNMP access for $ip..."
    
    # Check for snmpwalk command
    if ! command -v snmpwal    i/dev/null; then
        echo "⚠️  Warning: 'snmpwalk' command not found. Please install net-snmp."
        echo "   On macOS with Homebrew: brew install net-snmp"
        return
    fi

    # Common SNMP community strings
    communities=("public" "private" "admin" "manager" "cisco" "default")
    
    for community in "${communities[@]}"; do
        echo "Trying community:   ommunity"
        
        # Get system info
        result=$(snmpget -v2c -c $community $ip 1.3.6.1.2.1.1.1.0 2>/dev/null)
        if [[ $? -eq 0 ]]; then
            echo "✅ SNMP access with community '$community'"
            echo "System info: $result"
            
            # Get more details
            echo "Getting interface info..."
            snmpwalk -v2c -c $community $ip 1.3.6.1.2.1.2.2.1.2 2>/dev/null | head -10
            
            break
        fi
    done
}

# Default credential attempts
try_default_creds() {
    local ip=$1
    echo "🔑   mmon default credentials for switches..."
    
    echo "Cisco switches:"
    echo "  admin/admin, cisco/cisco, admin/cisco, admin/(blank)"
    
    echo "Netgear switches:"
    echo "  admin/password, admin/1234, admin/(blank)"
    
    echo "HP/Aruba switches:"
    echo "  admin/admin, manager/manager, admin/(blank)"
    
    echo "Dell switches:"
    echo "  ad  n/admin, root/calvin, admin/password"
    
    e    e    e    e    e    e    e    e    e  blank), admin/admin, Admin/Admin"
                                                                                echo ""
    echo "⚠️  ALWAYS CHANGE DEFAULT PASSWORDS IMMEDIATELY!"
}

# Port scanning for switch management
detailed_port_scan() {
    local ip=$1
    echo "🔍 Detailed port scan for $ip..."
    
    # Scan common switch management ports
    nmap -sS -sV -p 21,22,23,53,80,161,162,443,514,8080,8443,9000-9010 $ip
    
    echo ""
    echo "Service detection complete."
}

# Switch configuration backup (if accessible)
backup_swibackup_swibackup_swibackup_swibackup_swibackup_swibackug configuration backup for $ip..."
    
    echo "For different switch types:"
    echo ""
    echo "C   o (via SSH):"
    echo "  ssh admin@$ip 'show running-config' > cisco_backup_$ip.cfg"
    
    echo "HP/Aruba (via SSH):"
    echo "  ssh manager@$ip 'show config' > hp_backup_$ip.cfg"
    
    echo "Netgear (via TFTP if enabled):"
    echo "  Use web interface: Maintenance -> Upload/Download"
    
    echo ""
    echo "📁 Backup files will be saved in current directory"
}

# Security assessment
security_assessment() {
    local ip=$1
    echo "🛡️  Security assessment for $ip..."
    
    # Check for common vulnerabilities
    ec    ec    ec    ec   on switch vulnerabilities..."
    
    # Weak protocols
    if nc -z -w5 $ip 23 2>/dev/null; then
        echo         echo         echo         echo         echo         echo          -w5 $ip 21 2>/dev/null; then
        echo "⚠️  WARNING: FTP enabled"
    fi
    
    # SNMP check
    if snmpget -v1 -c public $ip 1.3.6.1.2.1.1.1.0 2>/dev/null; then
        echo "⚠️  CRITICAL: SNMP with default community 'public'"
    fi
    
    # Web    # Web    # Web    # if curl -k -s https://$ip | grep -qi "self-signed\|invalid certificate"; then
        echo "⚠️  WARNING: Self-signed SSL certificate"
    fi
    
    echo ""
    echo "Security recommendations:"
    echo "1. Disable Telnet, use SSH only"
    echo "2. Change default SNMP communities"  
    echo "3. Use strong admin passwords"
    echo "4. Enable HTTPS with valid certificates"
    echo "5. Restrict management access by IP"
                                                 VLAN conf                                      {
    echo "🌐 VLAN Configuration Helper"
    echo ""
    
    echo "Common VLAN s    echo "Common VLAN s    echo "Commonho "VLAN 10 - Management (192.168.10.0/24)"
    echo "VLAN 20 - Servers (192.168.20.0/24)"
    echo "VLAN 30 - Workstations (192.168.30.0/24)" 
    echo "VLAN 99 - Isolated/Quarantine (192.168.99.0/24)"
    echo ""
    
    echo "Sample Cisco commands:"
    ech    ech    ech    ech    ech    ech    ech    ech    ech    ech  interface vlan 10"
    echo "ip address 192.168.10.1 255.255.255.0"
    echo "exit"
    echo ""
    
    echo "Trunk configuration:"
    echo "interface gigabitethernet 1/1"
    echo "switchport mode trunk"
    echo "switchport trunk allowed vlan 10,20,30"
    echo "exit"
}

# Main menu
main_menu() {
    echo ""
    echo "🌐 MANAGED SWITCH TOOLKIT 🌐"
    echo ""
    echo "1. Discover switches on network"
    echo "2. Access specific switch"
    echo "3. Security assessment"
    echo "4. VLAN configuration helper"
    echo "5. Exit"
    echo ""
    
    read -p "Select option [1-5]: " choice
    
    case $choice in
        1)
            discover_switches
            ;;
        2)
            read -p "Enter switch IP address: " switch_ip
            echo ""
            try_web_interface $switch_ip
            echo ""
            try_cli_access $switch_ip
            echo ""
            try_snmp_access $switch_ip
            echo ""
            try_default_creds $switch_ip
            echo ""
            detailed_port_scan $switch_ip
            ;;
        3)
            read -p "Enter switch IP address: " switch_ip
            security_assessment $switch_ip
            ;;
        4)
            vlan_config_            vlan_config_            vlan_config_t 0
            ;;
        *)
            echo           pt            echo           pt            e    esac
    
    echo ""
    read -p "Press Enter to continue..."
    main_menu
}

# Check dependencies for macOS
check_deps() {
    echo "Checking for required tools..."
    check_command "nmap"
    check_command "curl"
    check_command "nc" "netcat"
}

# Main execution
if [[ $# -eq 0 ]]; then
    check_deps
    main_menu
else
    # C    # C    # C    # C    # C    # C    # C    # C    # over")
            check_deps
            discover_switches
            ;;
        "access")
            if [[ -n "$2" ]]; then
                                                  _interface $2
                try_cli_access $2  
                try_snmp_access $2
                try_default_creds $2
                                 echo "Usage: $0 access <switch_ip>"
            fi
            ;;
        "security")
                          ]]; then
                                                                              else
                     "                     "                     "                ;
        "vlan")
            vlan_config_helper
            ;;
        *)
              ho "Usage: $0 [scan|access <ip>|security <ip>|vlan]"
            echo "   or run without param            echo "   orode"
            ;;
    esac
fi

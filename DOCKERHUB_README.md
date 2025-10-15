# Switch Toolkit 🌐

A lightweight Docker container with comprehensive network switch management tools for discovery, access testing, and security assessment.

## Quick Start

```bash
docker run -it --rm --network host <your-username>/switch-toolkit
```

## Features

- **🔍 Network Discovery**: Automatically scan and discover managed switches on your network
- **🔐 Security Assessment**: Evaluate switch security configurations and identify vulnerabilities
- **📡 Multi-Protocol Support**: Test SSH, Telnet, HTTP/HTTPS, and SNMP access
- **🔑 Default Credentials Database**: Common default credentials for major switch manufacturers
- **🌐 VLAN Configuration Helper**: Sample configurations for common VLAN setups

## Usage Examples

### Interactive Mode (Default)
```bash
docker run -it --rm --network host <your-username>/switch-toolkit
```

### Discover Switches on Network
```bash
# Scan default subnet
docker run -it --rm --network host <your-username>/switch-toolkit discover

# Scan specific subnet
docker run -it --rm --network host <your-username>/switch-toolkit discover 192.168.1.0/24
```

### Access Specific Switch
```bash
docker run -it --rm --network host <your-username>/switch-toolkit access 192.168.1.100
```

### Security Assessment
```bash
docker run -it --rm --network host <your-username>/switch-toolkit security 192.168.1.100
```

### VLAN Configuration Helper
```bash
docker run -it --rm --network host <your-username>/switch-toolkit vlan
```

## Included Tools

- **nmap**: Network discovery and port scanning
- **curl**: Web interface testing
- **ssh-client**: SSH connectivity testing
- **telnet**: Legacy access testing
- **snmp**: SNMP protocol tools
- **netcat**: Generic TCP/UDP connectivity testing
- **iproute2 & net-tools**: Network configuration utilities

## Network Requirements

The container requires `--network host` flag to properly scan and interact with devices on your local network.

## Security Considerations

- This tool is designed for legitimate network administration
- Only use on networks you own or have explicit permission to test
- Contains tools that could be misused - use responsibly
- Default credentials should be changed immediately on production devices

## Container Details

- **Base Image**: Debian stable-slim
- **Size**: ~150MB
- **Architecture**: Multi-platform (amd64, arm64)

## Environment Variables

You can set the following environment variables:

```bash
# Skip banner display
docker run -e SHOW_BANNER=false --rm --network host <your-username>/switch-toolkit

# Set default subnet for scanning
docker run -e DEFAULT_SUBNET=10.0.0.0/24 --rm --network host <your-username>/switch-toolkit discover
```

## Common Use Cases

### Network Audit
Quickly identify all managed switches on your network and their management interfaces:
```bash
docker run -it --rm --network host <your-username>/switch-toolkit discover 10.0.0.0/16
```

### Pre-Configuration Check
Before configuring a new switch, verify connectivity and access methods:
```bash
docker run -it --rm --network host <your-username>/switch-toolkit access 192.168.1.1
```

### Security Compliance
Regular security assessments to ensure switches follow best practices:
```bash
for ip in 192.168.1.1 192.168.1.2 192.168.1.3; do
  docker run --rm --network host <your-username>/switch-toolkit security $ip
done
```

## Support

For issues, feature requests, or contributions, please visit the [GitHub repository](https://github.com/your-username/switch-toolkit).

## License

This tool is provided as-is for network administration purposes. Use at your own risk.

---

**Note**: Replace `<your-username>` with your actual Docker Hub username.
#!/usr/bin/env bash
# Installer for Linux VM
# - User install (default): ~/.local/bin and ~/.local/share/applications
# - System install (--system): /usr/local/bin and /usr/share/applications (requires sudo)

set -euo pipefail

usage() {
  cat <<'TXT'
Usage: ./install_linux_app.sh [--system]

Without flags, installs to user directories:
  - ~/.local/bin/switch-toolkit
  - ~/.local/share/applications/SwitchToolkit.desktop

With --system (requires sudo):
  - /usr/local/bin/switch-toolkit
  - /usr/share/applications/SwitchToolkit.desktop
TXT
}

prefix_user() {
  BIN_DIR="$HOME/.local/bin"
  APPS_DIR="$HOME/.local/share/applications"
}

prefix_system() {
  BIN_DIR="/usr/local/bin"
  APPS_DIR="/usr/share/applications"
}

main() {
  case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    --system) prefix_system ;;
    *) prefix_user ;;
  esac

  mkdir -p "$BIN_DIR" "$APPS_DIR"

  # Resolve repo paths
  script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")" && pwd)"
  repo_root="$(CDPATH= cd -- "$script_dir/.." && pwd)"

# Install wrapper
install -m 0755 "$script_dir/run_switch_toolkit.sh" "$BIN_DIR/switch-toolkit"

# Install Docker build context for the toolkit (Dockerfile + script)
if [ "$BIN_DIR" = "/usr/local/bin" ]; then
  DATA_DIR="/opt/switch-toolkit"
else
  DATA_DIR="$HOME/.local/share/switch-toolkit"
fi
mkdir -p "$DATA_DIR"
install -m 0644 "$repo_root/Dockerfile" "$DATA_DIR/Dockerfile"
install -m 0755 "$repo_root/switch_toolkit.sh" "$DATA_DIR/switch_toolkit.sh"

# Optional icon if provided
ICON_SRC="$script_dir/assets/switch-toolkit.png"
if [ -f "$ICON_SRC" ]; then
  if [ "$BIN_DIR" = "/usr/local/bin" ]; then
    ICON_DEST="/usr/share/icons/hicolor/256x256/apps"
  else
    ICON_DEST="$HOME/.local/share/icons/hicolor/256x256/apps"
  fi
  mkdir -p "$ICON_DEST"
  install -m 0644 "$ICON_SRC" "$ICON_DEST/switch-toolkit.png"
  ICON_LINE="Icon=switch-toolkit"
else
  ICON_LINE="# Icon not installed"
fi

# Write desktop entry with proper Exec path
cat > "$APPS_DIR/SwitchToolkit.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Switch Management Toolkit
Comment=Discover and assess managed switches on your network
Exec=$BIN_DIR/switch-toolkit
Terminal=true
Categories=Network;Utility;
$ICON_LINE
EOF

  echo "✅ Installed wrapper to: $BIN_DIR/switch-toolkit"
  echo "✅ Installed desktop entry to: $APPS_DIR/SwitchToolkit.desktop"
  echo "✅ Installed build context to: $DATA_DIR"
  echo
  echo "Next steps:"
  echo "- Ensure Docker is installed and running in the VM: https://docs.docker.com/engine/install/"
  echo "- You can start the toolkit via your app menu (Switch Management Toolkit) or run: switch-toolkit"
}

main "$@"

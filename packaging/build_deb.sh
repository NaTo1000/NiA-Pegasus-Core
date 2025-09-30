#!/usr/bin/env bash
# Build a Debian package for Switch Management Toolkit
# Usage: ./build_deb.sh [VERSION]
# Produces: dist/switch-toolkit_<VERSION>_all.deb

set -euo pipefail
VERSION="${1:-1.0.0}"
PKG_NAME="switch-toolkit"
WORK_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$WORK_DIR/.." && pwd)"
DIST_DIR="$REPO_ROOT/dist"
PKGROOT="$DIST_DIR/deb/pkgroot"
DEB_DIR="$PKGROOT/DEBIAN"

rm -rf "$DIST_DIR/deb" && mkdir -p "$DEB_DIR"

# Files layout
install -d "$PKGROOT/usr/local/bin"
install -d "$PKGROOT/usr/share/applications"
install -d "$PKGROOT/opt/$PKG_NAME"

# Optional icon
ICON_SRC="$WORK_DIR/assets/switch-toolkit.png"
if [ -f "$ICON_SRC" ]; then
  install -d "$PKGROOT/usr/share/icons/hicolor/256x256/apps"
  install -m 0644 "$ICON_SRC" "$PKGROOT/usr/share/icons/hicolor/256x256/apps/switch-toolkit.png"
  ICON_LINE="Icon=switch-toolkit"
else
  ICON_LINE=""
fi

# Binaries and data
install -m 0755 "$REPO_ROOT/linux/run_switch_toolkit.sh" "$PKGROOT/usr/local/bin/switch-toolkit"
install -m 0644 "$REPO_ROOT/Dockerfile" "$PKGROOT/opt/$PKG_NAME/Dockerfile"
install -m 0755 "$REPO_ROOT/switch_toolkit.sh" "$PKGROOT/opt/$PKG_NAME/switch_toolkit.sh"

# Desktop entry
cat > "$PKGROOT/usr/share/applications/SwitchToolkit.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Switch Management Toolkit
Comment=Discover and assess managed switches on your network
Exec=/usr/local/bin/switch-toolkit
Terminal=true
Categories=Network;Utility;
$ICON_LINE
EOF

# Control file
cat > "$DEB_DIR/control" <<EOF
Package: $PKG_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: bash, coreutils, docker.io | docker-ce | docker
Maintainer: NiA Pegasus <support@example.com>
Description: Switch Management Toolkit (Docker-based)
 A wrapper and desktop entry to build and run the Switch Management Toolkit
 in a Docker container with host networking.
EOF

# Build deb
mkdir -p "$DIST_DIR"
dpkg-deb --build "$PKGROOT" "$DIST_DIR/${PKG_NAME}_${VERSION}_all.deb"
echo "✅ Built: $DIST_DIR/${PKG_NAME}_${VERSION}_all.deb"

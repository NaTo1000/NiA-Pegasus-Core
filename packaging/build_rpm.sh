#!/usr/bin/env bash
# Build an RPM package for Switch Management Toolkit
# Usage: ./build_rpm.sh [VERSION]
# Produces: dist/switch-toolkit-<VERSION>-1.noarch.rpm

set -euo pipefail
VERSION="${1:-1.0.0}"
PKG_NAME="switch-toolkit"
WORK_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$WORK_DIR/.." && pwd)"
DIST_DIR="$REPO_ROOT/dist"
BUILD_DIR="$DIST_DIR/rpm/build"
ROOT_DIR="$BUILD_DIR/root"

rm -rf "$DIST_DIR/rpm" && mkdir -p "$ROOT_DIR"

# Layout
install -d "$ROOT_DIR/usr/local/bin"
install -d "$ROOT_DIR/usr/share/applications"
install -d "$ROOT_DIR/opt/$PKG_NAME"

# Optional icon
ICON_SRC="$WORK_DIR/assets/switch-toolkit.png"
ICON_LINE=""
if [ -f "$ICON_SRC" ]; then
  install -d "$ROOT_DIR/usr/share/icons/hicolor/256x256/apps"
  install -m 0644 "$ICON_SRC" "$ROOT_DIR/usr/share/icons/hicolor/256x256/apps/switch-toolkit.png"
  ICON_LINE="Icon=switch-toolkit"
fi

# Files
install -m 0755 "$REPO_ROOT/linux/run_switch_toolkit.sh" "$ROOT_DIR/usr/local/bin/switch-toolkit"
install -m 0644 "$REPO_ROOT/Dockerfile" "$ROOT_DIR/opt/$PKG_NAME/Dockerfile"
install -m 0755 "$REPO_ROOT/switch_toolkit.sh" "$ROOT_DIR/opt/$PKG_NAME/switch_toolkit.sh"

cat > "$ROOT_DIR/usr/share/applications/SwitchToolkit.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Switch Management Toolkit
Comment=Discover and assess managed switches on your network
Exec=/usr/local/bin/switch-toolkit
Terminal=true
Categories=Network;Utility;
$ICON_LINE
EOF

mkdir -p "$DIST_DIR"

if command -v fpm >/dev/null 2>&1; then
  echo "Using fpm to build RPM…"
  fpm -s dir -t rpm -n "$PKG_NAME" -v "$VERSION" \
      --architecture noarch \
      --description "Switch Management Toolkit (Docker-based)" \
      --depends "docker" \
      --license "MIT" \
      --url "https://example.com" \
      -C "$ROOT_DIR" \
      --package "$DIST_DIR/${PKG_NAME}-${VERSION}-1.noarch.rpm" \
      usr/local/bin/switch-toolkit \
      usr/share/applications/SwitchToolkit.desktop \
      opt/$PKG_NAME \
      $( [ -f "$ICON_SRC" ] && echo usr/share/icons/hicolor/256x256/apps/switch-toolkit.png )
  echo "✅ Built: $DIST_DIR/${PKG_NAME}-${VERSION}-1.noarch.rpm"
  exit 0
fi

if ! command -v rpmbuild >/dev/null 2>&1; then
  echo "❌ Neither fpm nor rpmbuild is installed. Install one of them and retry."
  echo "   - On Fedora/CentOS: sudo dnf install rpm-build or sudo yum install rpm-build"
  echo "   - Or: gem install --no-document fpm"
  exit 1
fi

# Use rpmbuild
RPMROOT="$BUILD_DIR/rpmbuild"
mkdir -p "$RPMROOT/BUILD" "$RPMROOT/RPMS" "$RPMROOT/SOURCES" "$RPMROOT/SPECS" "$RPMROOT/SRPMS"

# Create a tarball of the root dir as source
( cd "$ROOT_DIR" && tar czf "$RPMROOT/SOURCES/${PKG_NAME}-${VERSION}.tar.gz" . )

cat > "$RPMROOT/SPECS/${PKG_NAME}.spec" <<'SPEC'
%global debug_package %{nil}
Name:           switch-toolkit
Version:        VERSION_PLACEHOLDER
Release:        1%{?dist}
Summary:        Switch Management Toolkit (Docker-based)
License:        MIT
URL:            https://example.com
BuildArch:      noarch
Requires:       docker, bash, coreutils

%description
A wrapper and desktop entry to build and run the Switch Management Toolkit
in a Docker container with host networking.

%prep
%setup -q -c -T

%build
# nothing to build

%install
mkdir -p %{buildroot}/usr/local/bin
mkdir -p %{buildroot}/usr/share/applications
mkdir -p %{buildroot}/opt/switch-toolkit
mkdir -p %{buildroot}/usr/share/icons/hicolor/256x256/apps

# Extract files from the provided source tarball
cd %{buildroot}
%{__tar} xzf %{_sourcedir}/switch-toolkit-VERSION_PLACEHOLDER.tar.gz

%files
%defattr(-,root,root,-)
/usr/local/bin/switch-toolkit
/usr/share/applications/SwitchToolkit.desktop
/opt/switch-toolkit
/usr/share/icons/hicolor/256x256/apps/switch-toolkit.png

%changelog
* Tue Sep 30 2025 NiA Pegasus <support@example.com> - VERSION_PLACEHOLDER-1
- Initial package
SPEC

# Replace version placeholder in spec
sed -i "s/VERSION_PLACEHOLDER/$VERSION/g" "$RPMROOT/SPECS/${PKG_NAME}.spec"

rpmbuild --define "_topdir $RPMROOT" -bb "$RPMROOT/SPECS/${PKG_NAME}.spec"
# Move the rpm to dist
find "$RPMROOT/RPMS" -name "*.rpm" -exec mv {} "$DIST_DIR/" \;

echo "✅ Built RPM(s) in $DIST_DIR"

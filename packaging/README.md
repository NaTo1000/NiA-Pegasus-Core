# Packaging assets

Optional icon
- Place a 256x256 PNG icon at packaging/assets/switch-toolkit.png (or linux/assets/switch-toolkit.png). It will be included in both .deb and .rpm if present.

Build .deb
- Requirements: Debian/Ubuntu with dpkg-deb installed.
- Command:
  ./packaging/build_deb.sh 1.0.0
- Output: dist/switch-toolkit_1.0.0_all.deb

Build .rpm
- Option A (recommended): Install fpm
  - gem install --no-document fpm
  - ./packaging/build_rpm.sh 1.0.0
- Option B: rpmbuild
  - sudo dnf install rpm-build (Fedora) or sudo yum install rpm-build (CentOS)
  - ./packaging/build_rpm.sh 1.0.0
- Output: dist/switch-toolkit-1.0.0-1.noarch.rpm

Install
- Debian/Ubuntu:
  sudo apt install ./dist/switch-toolkit_1.0.0_all.deb
- Fedora/CentOS:
  sudo dnf install ./dist/switch-toolkit-1.0.0-1.noarch.rpm

After install
- Launch from your app menu: "Switch Management Toolkit"
- Or run from terminal: switch-toolkit

Uninstall
- Debian/Ubuntu: sudo apt remove switch-toolkit
- Fedora/CentOS: sudo dnf remove switch-toolkit

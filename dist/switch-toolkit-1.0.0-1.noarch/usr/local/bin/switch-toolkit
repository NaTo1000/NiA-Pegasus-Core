#!/usr/bin/env bash
# Switch Management Toolkit launcher for Linux (VM)
# - Builds the Docker image if missing
# - Runs the toolkit with --network host for accurate LAN scanning

set -euo pipefail

bold() { printf "\033[1m%s\033[0m\n" "$*"; }
need() { command -v "$1" >/dev/null 2>&1 || { echo "❌ Required command not found: $1"; exit 1; }; }

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/.." && pwd)"  # Dockerfile is at repo root

# Determine Docker build context. Prefer packaged context if present.
build_context() {
  if [ -d "/opt/switch-toolkit" ]; then
    echo "/opt/switch-toolkit"
  elif [ -d "$HOME/.local/share/switch-toolkit" ]; then
    echo "$HOME/.local/share/switch-toolkit"
  else
    echo "$repo_root"
  fi
}

ensure_image() {
  local ctx
  ctx="$(build_context)"
  if ! docker image inspect switch-toolkit:dev >/dev/null 2>&1; then
    bold "Building Docker image switch-toolkit:dev from context: $ctx …"
    if docker buildx version >/dev/null 2>&1; then
      docker buildx build -t switch-toolkit:dev --load "$ctx"
    else
      docker build -t switch-toolkit:dev "$ctx"
    fi
  fi
}

run_interactive() {
  exec docker run --rm -it --network host switch-toolkit:dev
}

run_discover_auto() {
  # With --network host, container will auto-detect host subnet
  exec docker run --rm --network host switch-toolkit:dev discover
}

run_discover_cidr() {
  local cidr="$1"
  exec docker run --rm --network host switch-toolkit:dev discover "$cidr"
}

run_access() {
  local ip="$1"
  docker run --rm --network host switch-toolkit:dev access "$ip"
  echo
  echo "Running security assessment…"
  exec docker run --rm --network host switch-toolkit:dev security "$ip"
}

main() {
  need docker
  ensure_image

  echo
  bold "🌐 Switch Management Toolkit (Linux)"
  echo "1) Interactive toolkit (container)"
  echo "2) Discover (auto-detected host subnet)"
  echo "3) Discover (custom CIDR)"
  echo "4) Access + Security assessment (single IP)"
  echo "5) Exit"
  printf "Select option [1-5]: "
  read -r choice
  case "$choice" in
    1) run_interactive ;;
    2) run_discover_auto ;;
    3) printf "Enter CIDR (e.g., 192.168.1.0/24): "; read -r cidr; run_discover_cidr "$cidr" ;;
    4) printf "Enter target IP: "; read -r ip; run_access "$ip" ;;
    5) exit 0 ;;
    *) echo "Invalid option" ;;
  esac
}

main "$@"

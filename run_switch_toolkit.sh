#!/usr/bin/env bash
# Wrapper to run the Switch Management Toolkit from macOS Terminal
set -euo pipefail

bold() { printf "\033[1m%s\033[0m\n" "$*"; }

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "❌ Required command not found: $1"
    exit 1
  fi
}

build_image_if_needed() {
  if ! docker image inspect switch-toolkit:dev >/dev/null 2>&1; then
    bold "Building Docker image switch-toolkit:dev (first-time setup)…"
    docker buildx build -t switch-toolkit:dev --load "$(dirname "$0")"
  fi
}

host_subnet() {
  local iface ip
  iface=$(route -n get default 2>/dev/null | awk '/interface:/{print $2}' || true)
  if [ -n "${iface:-}" ]; then
    ip=$(ipconfig getifaddr "$iface" 2>/dev/null || true)
  fi
  if [ -z "${ip:-}" ]; then
    for i in en0 en1 en2; do
      ip=$(ipconfig getifaddr "$i" 2>/dev/null || true)
      [ -n "$ip" ] && break
    done
  fi
  if [ -n "${ip:-}" ]; then
    printf "%s.%s.%s.0/24" "${ip%%.*}" "${ip#*.%%?}" "${ip#*.*.%%?}"
  fi
}

# Safer dotted-quad split for /24
host_subnet() {
  local iface ip a b c
  iface=$(route -n get default 2>/dev/null | awk '/interface:/{print $2}' || true)
  if [ -n "${iface:-}" ]; then
    ip=$(ipconfig getifaddr "$iface" 2>/dev/null || true)
  fi
  if [ -z "${ip:-}" ]; then
    for i in en0 en1 en2; do
      ip=$(ipconfig getifaddr "$i" 2>/dev/null || true)
      [ -n "$ip" ] && break
    done
  fi
  if [ -n "${ip:-}" ]; then
    IFS=. read -r a b c _ <<EOF
$ip
EOF
    printf "%s.%s.%s.0/24" "$a" "$b" "$c"
  fi
}

main() {
  need docker
  # Ensure buildx exists (Docker Desktop usually provides it)
  if ! docker buildx version >/dev/null 2>&1; then
    echo "ℹ️  docker buildx not found; attempting regular build"
    if ! docker image inspect switch-toolkit:dev >/dev/null 2>&1; then
      docker build -t switch-toolkit:dev "$(dirname "$0")"
    fi
  else
    build_image_if_needed
  fi

  echo ""
  bold "🌐 Switch Management Toolkit"
  echo "1) Interactive toolkit (in container)"
  echo "2) Discover (auto-detected host subnet)"
  echo "3) Discover (custom CIDR)"
  echo "4) Security assessment (single IP)"
  echo "5) Exit"
  printf "Select option [1-5]: "
  read -r choice
  case "$choice" in
    1)
      exec docker run --rm -it switch-toolkit:dev
      ;;
    2)
      cidr=$(host_subnet || true)
      if [ -n "${cidr:-}" ]; then
        echo "Using host subnet: $cidr"
        exec docker run --rm switch-toolkit:dev discover "$cidr"
      else
        echo "Could not auto-detect subnet; falling back to container autodetect"
        exec docker run --rm switch-toolkit:dev discover
      fi
      ;;
    3)
      printf "Enter CIDR (e.g., 192.168.1.0/24): "
      read -r cidr
      exec docker run --rm switch-toolkit:dev discover "$cidr"
      ;;
    4)
      printf "Enter target IP: "
      read -r ip
      echo "Running access helpers…"
      docker run --rm switch-toolkit:dev access "$ip"
      echo ""
      echo "Running security assessment…"
      exec docker run --rm switch-toolkit:dev security "$ip"
      ;;
    5)
      exit 0
      ;;
    *)
      echo "Invalid option"
      ;;
  esac
}

main "$@"

#!/usr/bin/env bash
set -euo pipefail

echo "== GPS App Locator =="
echo

probe_cmd() {
  local name="$1"
  local cmd="$2"
  if command -v "$cmd" >/dev/null 2>&1; then
    printf "[FOUND] %-16s command: %s (%s)\n" "$name" "$cmd" "$(command -v "$cmd")"
  else
    printf "[MISS ] %-16s command: %s\n" "$name" "$cmd"
  fi
}

probe_cmd "Navit" "navit"
probe_cmd "Pure Maps" "pure-maps"
probe_cmd "Pure Maps" "puremaps"
probe_cmd "Organic Maps" "organicmaps"
probe_cmd "Organic Maps" "omaps"
probe_cmd "PyGPSClient" "pygpsclient"

echo
if command -v flatpak >/dev/null 2>&1; then
  echo "-- Flatpak app matches --"
  flatpak list --app --columns=application,name | grep -Ei 'pure|organic|osmscout|navit|gps' || true
else
  echo "flatpak not installed"
fi

echo
if command -v grep >/dev/null 2>&1; then
  echo "-- Desktop entries mentioning nav apps --"
  grep -Eirl 'pure|organic|osmscout|navit|gps' /usr/share/applications ~/.local/share/applications 2>/dev/null | head -n 50 || true
fi

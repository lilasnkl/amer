#!/bin/sh
# Amer installer for macOS / Linux / Git Bash: sh install.sh [--only claude,omp,antigravity] [--uninstall]
cd "$(dirname "$0")" || exit 1
for py in python3 python py; do
  if command -v "$py" >/dev/null 2>&1; then
    exec "$py" install.py "$@"
  fi
done
echo "Python 3 was not found. Install it from https://www.python.org/downloads/ and run this again."
exit 1

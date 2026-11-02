#!/bin/sh
set -eu
cd "$(dirname "$0")/frontend"
if [ ! -d node_modules ]; then npm ci; fi
exec npm run dev -- --host 0.0.0.0

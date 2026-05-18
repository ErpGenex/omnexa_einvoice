#!/usr/bin/env bash
# Update omnexa_einvoice + omnexa_core for cloud USB signing on a Frappe bench.
set -euo pipefail
BENCH="${BENCH_ROOT:-$HOME/frappe-bench}"
SITE="${1:-}"

cd "$BENCH"

pull_app() {
	local app="$1"
	if [[ -d "apps/$app/.git" ]]; then
		echo "==> git pull $app"
		git -C "apps/$app" pull --ff-only
	else
		echo "WARN: apps/$app is not a git repo — install/update manually"
	fi
}

pull_app omnexa_einvoice
pull_app omnexa_core

bench migrate
bench build --apps omnexa_einvoice,omnexa_core

if [[ -n "$SITE" ]]; then
	bench --site "$SITE" clear-cache
	bench --site "$SITE" execute "import frappe; from omnexa_einvoice import SIGNING_BRIDGE_RELEASE; print('SIGNING_BRIDGE_RELEASE', SIGNING_BRIDGE_RELEASE)"
fi

bench restart
echo "Done. On Windows PC: Ctrl+Shift+R in browser, then Branch → Test cloud ↔ PC signing."
echo "Expected release: 20260518.5 (check Branch dashboard indicator)."

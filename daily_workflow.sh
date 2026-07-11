#!/usr/bin/env bash
#
# Daily Wheel-scanner workflow (run via the desktop shortcut or Git Bash):
#   1. Log VIX + show regime          (vix_monitor.py)
#   2. Refresh earnings calendar CSV  (earnings_monitor.py — cached, cheap warm)
#   3. Scan for Wheel candidates      (main.py wheel — needs MooMoo OpenD running)
#   4. Open the scan_results folder in Explorer, newest CSV selected
#
# Usage:
#   ./daily_workflow.sh                # live run (default --capital 8900)
#   ./daily_workflow.sh --capital 6700 # custom position sizing
#   ./daily_workflow.sh --mock         # offline test run (no OpenD needed)

set -u
cd "$(dirname "$0")"

CAPITAL=8900
MOCK=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --capital) CAPITAL="$2"; shift 2 ;;
        --mock)    MOCK="--mock"; shift ;;
        *)         echo "Unknown option: $1"; exit 1 ;;
    esac
done

banner() { printf '\n=== %s ===\n' "$1"; }

banner "1/3 VIX regime (logging to reports/vix)"
python vix_monitor.py || echo "[WARN] VIX check failed - continuing"

banner "2/3 Earnings calendar (reports/earnings)"
python earnings_monitor.py || echo "[WARN] Earnings calendar failed - continuing"

banner "3/3 Wheel scan (capital \$${CAPITAL}/position)"
before_newest=$(ls -t scan_results/wheel_candidates_*.csv 2>/dev/null | head -1)

python main.py $MOCK wheel --capital "$CAPITAL"

after_newest=$(ls -t scan_results/wheel_candidates_*.csv 2>/dev/null | head -1)

if [[ -n "$after_newest" && "$after_newest" != "$before_newest" ]]; then
    banner "Results: $after_newest"
    # Open Explorer with the fresh CSV selected (explorer's exit code is noise)
    explorer.exe /select,"$(cygpath -w "$after_newest")" || true
else
    echo
    echo "[INFO] No new scan CSV produced (no candidates, --no-csv, or scan failed)"
    echo "       Nothing to open."
fi

echo
read -rp "Done. Press Enter to close..."

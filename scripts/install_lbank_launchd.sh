#!/bin/zsh
set -euo pipefail

ROOT="/Users/ceciliamiao/Documents/交易策略-Crypto/github-v7-MEME-strategy"
RUNNER_DIR="$HOME/lbank-strategy-runner"
RUNNER="$RUNNER_DIR/run_lbank_workflow.sh"
RUNNER_REPO="$RUNNER_DIR/repo_work"
LAUNCH_DIR="$HOME/Library/LaunchAgents"
USER_ID="$(id -u)"

mkdir -p "$LAUNCH_DIR" "$ROOT/logs/lbank_paper" "$RUNNER_DIR"
chmod +x "$ROOT/scripts/run_lbank_workflow.sh"
mkdir -p "$RUNNER_REPO"
/usr/bin/rsync -a --exclude ".git" "$ROOT/" "$RUNNER_REPO/"

cat > "$RUNNER" <<'EOF'
#!/bin/zsh
set -u

REPO="$HOME/lbank-strategy-runner/repo_work"
COMMAND="${1:-review-all}"
LOG_DIR="$HOME/lbank-strategy-runner/logs"
LOG_FILE="$LOG_DIR/${COMMAND}.log"

mkdir -p "$LOG_DIR"

{
  echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') START $COMMAND ====="
  cd "$REPO" || exit 1
  if [[ "$COMMAND" == "health-check" ]]; then
    /usr/bin/python3 scripts/lbank_health_check.py
  elif [[ "$COMMAND" == "mtf-long-notify" ]]; then
    /usr/bin/python3 scripts/lbank_multitimeframe_backtest.py notify config/strategies/quality8_multitimeframe_atr_long_filtered.json
  else
    /usr/bin/python3 scripts/lbank_paper_trader.py "$COMMAND"
  fi
  exit_code=$?
  echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') END $COMMAND status=$exit_code ====="
  exit $exit_code
} >> "$LOG_FILE" 2>&1
EOF
chmod +x "$RUNNER"

for plist in "$ROOT"/launchd/com.cecily626.lbank.*.plist; do
  plutil -lint "$plist" >/dev/null
  target="$LAUNCH_DIR/$(basename "$plist")"
  cp "$plist" "$target"
  launchctl bootout "gui/$USER_ID" "$target" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$USER_ID" "$target"
  launchctl enable "gui/$USER_ID/$(basename "$plist" .plist)"
  echo "Installed $(basename "$plist")"
done

echo
echo "Installed LBank local schedules:"
echo "- daily signal: 20:15"
echo "- morning review: 08:00"
echo "- multitimeframe long observer: every 60 minutes"
echo "- health check: every 60 minutes"
echo "- weekly review: Sunday 08:15"
echo
echo "Logs:"
echo "$RUNNER_DIR/logs/"

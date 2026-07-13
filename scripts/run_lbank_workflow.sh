#!/bin/zsh
set -u

ROOT="$HOME/lbank-strategy-runner/repo_work"
COMMAND="${1:-review-all}"
LOG_DIR="$HOME/lbank-strategy-runner/logs"
LOG_FILE="$LOG_DIR/${COMMAND}.log"

mkdir -p "$LOG_DIR"

{
  echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') START $COMMAND ====="
  cd "$ROOT" || exit 1
  if [[ "$COMMAND" == "mtf-long-notify" ]]; then
    /usr/bin/python3 scripts/lbank_multitimeframe_backtest.py notify config/strategies/quality8_multitimeframe_atr_long_filtered.json
  else
    /usr/bin/python3 scripts/lbank_paper_trader.py "$COMMAND"
  fi
  exit_code=$?
  echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') END $COMMAND status=$exit_code ====="
  exit $exit_code
} >> "$LOG_FILE" 2>&1

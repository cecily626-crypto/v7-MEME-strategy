# OpenClaw Runtime Map

## V7

Agent ID：

market-analyst-v2

运行 prompt：

/home/ubuntu/.openclaw/agents/market-analyst-v2/workspace/AGENTS.md

V7 策略包：

/home/ubuntu/.openclaw/skills/initial_long_strategy_v2_v7/SKILL.md

V7 条件提醒脚本：

/home/ubuntu/.openclaw/tools/v7_signal_alert_watch.py

V7 条件提醒日志：

/tmp/v7_signal_alert_watch.log

## MEME-BIDIR

观察脚本：

/home/ubuntu/.openclaw/tools/meme_bidir_live_observe_watch.py

观察 JSON：

/home/ubuntu/.openclaw/skills/high_risk_short_strategy_v1/meme_bidir_live_observe_latest.json

观察 Markdown：

/home/ubuntu/.openclaw/skills/high_risk_short_strategy_v1/meme_bidir_live_observe_latest.md

日志：

/home/ubuntu/.openclaw/logs/meme_bidir_live_observe.log

## Cron 注意事项

cron 必须包含 node 路径，否则 V7 agent 可能报错：

exec: node: not found

建议 crontab 顶部包含：

PATH=/home/ubuntu/.nvm/versions/node/v22.22.3/bin:/home/ubuntu/.local/share/pnpm:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

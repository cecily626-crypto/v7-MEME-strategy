# Crypto Strategy Skills

本仓库用于保存可迁移的加密货币交易策略 skill。

目标：

- 从 OpenClaw 迁移到 Claude Code 或其他 Agent 时，无需从头解释策略
- 换服务器时可以快速恢复策略规则
- 保留 V7 与 MEME-BIDIR 的边界
- 防止策略规则、回测结果、Telegram 文案散落在多个文件中

## 当前策略

1. skills/V7_LONG_SKILL.md  
   BTC / ETH 稳健做多策略，只做多，不做空。

2. skills/MEME_BIDIR_SKILL.md  
   memecoin / 高波动山寨双向观察策略，当前不是正式开仓提醒，默认仓位 0%。

3. scripts/lbank_paper_trader.py  
   V7 做多方向的 LBank 纸面账户监控脚本，用于每日信号、次日 08:00 复盘和 2000 USDT 模拟账户记录。

## 快速查阅

- docs/CURRENT_TRADING_STRATEGY.md  
  当前 LBank V7-P 做多纸面账户策略说明。

- docs/DAILY_SIGNAL_AND_REVIEW.md  
  每日 Telegram 信号和早上 08:00 复盘流程。

## 重要纪律

- V7 不做空
- 当前 LBank paper monitor 也只做多，做空模块后续单独开发
- MEME-BIDIR 当前不自动开仓
- 数据缺失不得强行给正式开仓建议
- 资金面不通过不得给非 0% 仓位
- 技术面不通过不得给非 0% 仓位
- 观察状态仓位必须 0%

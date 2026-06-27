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

## 重要纪律

- V7 不做空
- MEME-BIDIR 当前不自动开仓
- 数据缺失不得强行给正式开仓建议
- 资金面不通过不得给非 0% 仓位
- 技术面不通过不得给非 0% 仓位
- 观察状态仓位必须 0%

# LBank 纸面交易与 Telegram 推送

## 当前版本

- 策略方向：只做多。
- 做空模块：后续单独开发，不混入当前策略。
- 数据源：LBank 现货日线 `/v2/kline.do`。
- 账户规模：2000 USDT 纸面账户。
- 推送渠道：Telegram bot `青铜c`。

## Telegram 配置

复制 `.env.example` 为 `.env`，填入：

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

`.env` 已被 `.gitignore` 忽略，不会提交到 GitHub。

## 命令

```bash
python3 scripts/lbank_paper_trader.py simulate
python3 scripts/lbank_paper_trader.py signal
python3 scripts/lbank_paper_trader.py review
```

`signal` 用于每天收盘后生成下一交易日目标仓位。  
`review` 用于每天早上 8 点复盘前一日，并更新 30 日纸面账户表现。

## 资金费率

LBank 合约行情文档中的 `marketData` 返回字段包含 `prePositionFeeRate`。当前环境访问合约公开行情接口返回 403，因此脚本会：

1. 优先读取 LBank 合约资金费率。
2. 如果不可用，复盘中标记为不可用。
3. 纸面账户暂按 0 资金费率计算。

实盘前必须再次确认 LBank 合约 API 可访问性、具体合约 symbol、资金费率结算时间和手续费档位。


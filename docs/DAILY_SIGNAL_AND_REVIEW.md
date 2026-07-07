# 每日信号与复盘流程

## 每日会发生什么

当前系统有三个自动任务：

1. 每日交易信号
2. 次日早上日复盘
3. 每周复盘

所有内容都会通过新的 Telegram bot 推送，不再和旧的青铜C内容混在一起。

## 每日交易信号

时间：

```text
每天 20:15 America/New_York
```

作用：

- 读取 LBank 日线数据
- 分别计算两个策略的目标仓位
- 推送是否持仓、持有哪些币、每个币目标权重
- 推送新增 / 加仓 / 减仓 / 清仓动作
- 如果没有机会，推送空仓

信号示例：

```text
LBank 策略信号: QUALITY8 混合杠杆 + 放量1.5倍
日期: 2026-07-05
纸账户: 1860.13 USDT
放量条件: 1.5x / 杠杆: 3x/5x
目标名义仓位:
- xlm_usdt: 150.00%
动作:
- 新增 xlm_usdt: 0.00% -> 150.00%
```

## 日复盘

时间：

```text
每天 08:00 America/New_York
```

作用：

- 分别更新两个 30 日纸面账户结果
- 复盘前一日策略表现
- 输出当前权益、盈亏、最大回撤、交易数、胜率、费用和当前目标仓位

复盘示例：

```text
LBank 日复盘: 6币现货 + 放量1.2倍
区间: 2026-06-06 至 2026-07-05
初始: 2000.00 USDT
当前: 2000.00 USDT
盈亏: +0.00 USDT (+0.00%)
最大回撤: 0.00%
交易数: 0
胜率: 暂无%
当前目标名义仓位: 空仓
```

## 周复盘

时间：

```text
每周日 08:15 America/New_York
```

作用：

- 汇总两个策略的 30 日纸账户结果
- 检查是否出现爆仓事件、连续亏损或异常费用
- 给下周继续观察的状态提示

## 当前自动任务

已启用：

- `lbank-crypto-long-only-daily-signal`
- `lbank-crypto-paper-account-morning-review`
- `lbank-dual-strategy-weekly-review`

运行目录：

```text
/Users/ceciliamiao/Documents/交易策略-Crypto/github-v7-MEME-strategy
```

实际命令：

```text
python3 scripts/lbank_paper_trader.py signal-all
python3 scripts/lbank_paper_trader.py review-all
python3 scripts/lbank_paper_trader.py weekly-all
```

## 数据异常处理

如果 LBank 某个交易对临时请求失败，脚本会优先使用本地缓存，避免整条 Telegram 推送失败。

如果资金费率接口不可用，杠杆策略会按配置的日资金费率估算。

## 旧青铜C推送

旧青铜C每日推送目前没有确认停掉，因为它不是由当前 Codex automation 管理的。新的策略推送已经使用新 Telegram bot，避免和旧内容混在一起。

如果要停旧推送，需要到旧系统里查：

- OpenClaw 定时任务
- 服务器 crontab
- Telegram bot 后台
- 其他自动化服务


# LBank 本机健康检查

健康检查用于发现本机定时任务失联。它不判断策略是否赚钱，也不要求一定有交易信号，只检查关键任务最近是否成功运行并完成 Telegram 推送。

## 检查规则

- 每日复盘 `review-all`: 30 小时内必须成功一次
- 晚间信号 `signal-all`: 30 小时内必须成功一次
- 多周期小时观察 `mtf-long-notify`: 2.5 小时内必须成功一次
- 周复盘 `weekly-all`: 8 天内必须成功一次

健康检查每小时运行一次。发现异常时会通过 Telegram 发告警；同一异常 6 小时内不会重复刷屏。

## 本机安装

每次策略代码、配置、健康检查脚本有更新后，执行：

```bash
cd "/Users/ceciliamiao/Documents/交易策略-Crypto/github-v7-MEME-strategy"
./scripts/install_lbank_launchd.sh
```

安装后会创建或更新：

- `com.cecily626.lbank.daily-signal`
- `com.cecily626.lbank.morning-review`
- `com.cecily626.lbank.mtf-long-observer`
- `com.cecily626.lbank.weekly-review`
- `com.cecily626.lbank.health-check`

## 手动检查

```bash
/Users/ceciliamiao/lbank-strategy-runner/run_lbank_workflow.sh health-check
tail -n 80 /Users/ceciliamiao/lbank-strategy-runner/logs/health-check.log
```

如果需要确认 Telegram 通道本身能收到“正常”消息，可以临时执行：

```bash
cd /Users/ceciliamiao/lbank-strategy-runner/repo_work
/usr/bin/python3 scripts/lbank_health_check.py --send-ok
```

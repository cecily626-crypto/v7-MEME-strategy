# MEME-BIDIR Strategy Skill

## 1. 策略定位

MEME-BIDIR 是 memecoin / 高波动山寨币双向观察策略。

策略方向：

- 做多观察
- 做空观察
- 双向监控
- 当前不是正式开仓提醒
- 当前仓位 0%

策略边界：

- 不是 V7 BTC/ETH 稳健做多策略
- 不继承 V7 的胜率、Profit Factor、最大回撤、交易次数或 total_r
- 不继承 HR-SHORT V1E 的做空绩效
- 当前不等于正式交易策略
- 只有完成独立回测、风控和仓位规则后，才可以升级为正式开仓提醒

## 2. 与 V7 的边界

V7 是 BTC / ETH 稳健做多策略，只做多，不做空。

MEME-BIDIR 是 memecoin / 高波动山寨币双向观察策略，可以观察做多和做空，但当前不是正式开仓提醒。

严禁：

- 把 MEME-BIDIR 观察信号说成 V7 信号
- 把 MEME-BIDIR 观察信号说成正式开仓提醒
- 用 V7 回测结果证明 MEME-BIDIR 有效
- 用 HR-SHORT V1E 做空绩效证明 MEME-BIDIR 双向策略有效
- 在数据缺失时给正式开仓建议


## 3. 当前 OpenClaw 运行文件位置

当前观察脚本：

`/home/ubuntu/.openclaw/tools/meme_bidir_live_observe_watch.py`

当前观察 JSON：

`/home/ubuntu/.openclaw/skills/high_risk_short_strategy_v1/meme_bidir_live_observe_latest.json`

当前观察 Markdown：

`/home/ubuntu/.openclaw/skills/high_risk_short_strategy_v1/meme_bidir_live_observe_latest.md`

当前日志：

`/home/ubuntu/.openclaw/logs/meme_bidir_live_observe.log`

当前脚本中 calc_entry_plan 函数提取状态：

- 已提取


## 4. 数据源

当前 MEME-BIDIR 观察报告使用：

CoinGlass：

- spot pairs-markets
- 成交额
- 1h / 4h / 12h / 24h 涨跌幅
- 4h 成交量变化
- 4h 净流入，如可用

LBank futures live marketData：

- last
- open
- high
- low
- 24h change
- high pump
- pullback from high
- range
- funding
- turnover

如最近3根已收盘4H K线 high / low 缺失，止损建议不得输出具体价格，必须提示暂不建议正式开仓。

## 5. 报告状态纪律

做多观察时必须写：

- 状态：做多观察，不是正式开仓提醒，当前仓位 0%。

做空观察时必须写：

- 状态：做空观察，不是正式开仓提醒，当前仓位 0%。

禁止写：

- 建议开仓
- 正式开仓提醒
- 当前可以进场
- 强买入
- 强做空
- 当前仓位非 0%

除非未来完成独立回测、风控和仓位规则，否则所有 MEME-BIDIR 报告必须保持观察状态。

## 6. 做多观察输出格式

建议执行：

- 状态：做多观察，不是正式开仓提醒，当前仓位 0%。

- 优先回踩观察区间：{pullback_low} - {pullback_high}
  条件：价格先回踩进入该区间；若不跌破 {pullback_low}，并在区间内出现止跌/重新走强信号，可考虑区间内低吸观察；跌破 {pullback_low} 则不入场。

- 回踩确认价：{pullback_high} 上方
  条件：重新站上 {pullback_high} 说明回踩确认成功；若已明显拉离 {pullback_high}，不追高。

- 备选突破入场：{breakout_price} 上方
  条件：4H 有效站上 {breakout_price} 后，回踩不跌破 {breakout_price} 再考虑；直接拉升不追。

- 止损建议：
  回踩入场止损：{pullback_stop_price}
  突破入场止损：{breakout_stop_price}

- 失效参考：
  跌破 {risk_invalid_price} 后，当前做多观察失效，重新评估。

## 7. 做空观察输出格式

建议执行：

- 状态：做空观察，不是正式开仓提醒，当前仓位 0%。

- 优先反弹观察区间：{rebound_low} - {rebound_high}
  条件：价格先反弹进入该区间；若不能有效突破 {rebound_high}，并在区间内出现承压/重新走弱信号，可考虑区间内反弹做空观察；突破 {rebound_high} 则不入场。

- 反弹确认价：{rebound_low} 下方
  条件：重新跌回 {rebound_low} 下方，说明反弹失败确认；若已明显跌离 {rebound_low}，不追空。

- 备选跌破入场：{breakdown_price} 下方
  条件：4H 有效跌破 {breakdown_price} 后，反抽不重新站回 {breakdown_price} 上方再考虑；直接下杀不追。

- 止损建议：
  反弹入场止损：{rebound_stop_price}
  跌破入场止损：{breakdown_stop_price}

- 失效参考：
  突破 {risk_invalid_price} 后，当前做空观察失效，重新评估。

## 8. 止损价格计算规则

止损建议必须直接输出具体价格，不能只输出公式。

每次生成 MEME-BIDIR Telegram 报告前，必须先计算：

avg_range_3h4 = mean(high - low, 最近3根已收盘4H K线)

做多：

- 回踩入场止损 = 回踩区间下沿 - avg_range_3h4
- 突破入场止损 = 突破确认价 - avg_range_3h4

做空：

- 反弹入场止损 = 反弹区间上沿 + avg_range_3h4
- 跌破入场止损 = 跌破确认价 + avg_range_3h4

如果最近3根4H K线数据缺失，必须输出：

- 止损建议：最近3根4H区间数据缺失，暂不建议正式开仓。

禁止只输出：

- SL = 实际入场价 - 最近3根4H平均价格区间
- 止损 = 回踩区间下沿 - avg_range_3h4
- 止损参考最近3根4H平均波动

## 9. 入场区间与确认价解释

做多：

- 优先回踩观察区间不是“突破后追入区间”
- 它表示价格先回落到该区间后观察是否止跌
- 区间下沿是防守位
- 区间上沿是回踩确认价
- 可以在区间内出现止跌/重新走强信号时低吸观察
- 重新站上区间上沿只代表回踩确认成功
- 如果价格已经明显拉离区间上沿，不追高

做空：

- 优先反弹观察区间不是“跌破后追空区间”
- 它表示价格先反弹到该区间后观察是否承压
- 区间上沿是防守位
- 区间下沿是反弹失败确认价
- 可以在区间内出现承压/重新走弱信号时反弹做空观察
- 重新跌回区间下沿下方只代表反弹失败确认
- 如果价格已经明显跌离区间下沿，不追空

## 10. 当前入场区间计算逻辑

当前 OpenClaw 脚本中，入场观察区间沿用 LBank live marketData 的 last / high / low 估算。

如果 high 和 low 有效：

range_abs = high - low

如果 high / low 缺失：

range_abs = abs(last) × 0.02

做多：

- pullback_high = last - 0.10 × range_abs
- pullback_low = last - 0.25 × range_abs
- breakout_ref = max(high, last × 1.003)
- risk_ref = max(last - 0.40 × range_abs, low)

做空：

- retest_low = last + 0.10 × range_abs
- retest_high = last + 0.25 × range_abs
- breakdown_ref = last × 0.997
- invalid_ref = min(last + 0.40 × range_abs, high)

注意：

- 这是观察区间计算，不是正式回测入场规则
- 后续如果升级为正式策略，需要把这些区间规则纳入独立回测
- 不得把当前观察区间等同于已验证交易策略

## 11. Telegram 报告必须包含的信息

MEME-BIDIR Telegram 报告建议包含：

- 策略名称：MEME-BIDIR
- 币种
- 方向：做多观察 / 做空观察
- 状态：不是正式开仓提醒，当前仓位 0%
- 池子 / 信号来源
- 数据源
- 得分
- 当前价
- 1h / 4h / 12h / 24h 涨跌幅
- 24h 成交额
- 4h 成交量变化
- 4h 净流入，如可用
- LBank last / open / high / low
- LBank 24h change / high_pump / pullback / range
- LBank Funding
- LBank turnover
- 建议执行
- 入场观察区间
- 确认价
- 备选突破或跌破入场
- 止损建议
- 失效参考
- 触发原因
- 下一步说明


## 12. 当前 OpenClaw calc_entry_plan 实现参考

```python
def calc_entry_plan(x):
    """
    MEME-BIDIR 入场观察与止损建议。

    规则：
    1. 只输出观察计划，不是正式开仓提醒。
    2. 当前仓位固定 0%。
    3. 止损建议必须输出具体价格，不允许只输出公式。
    4. 止损基于最近3根已收盘4H K线平均价格区间：
       avg_range_3h4 = mean(high - low, 最近3根已收盘4H K线)
    5. 如果最近3根4H区间数据缺失，则不建议正式开仓。
    """
    side = x.get("side")
    m = x.get("market") or {}
    lb = x.get("lbank") or {}

    last = lb.get("last")
    if last is None:
        last = m.get("price")

    high = lb.get("high")
    low = lb.get("low")
    open_price = lb.get("open")

    def to_float(v):
        try:
            if v is None:
                return None
            return float(v)
        except Exception:
            return None

    last = to_float(last)
    high = to_float(high)
    low = to_float(low)
    open_price = to_float(open_price)

    def fmt(v):
        try:
            return f"{float(v):.8g}"
        except Exception:
            return "NA"

    def get_avg_range_3h4():
        candidates = [
            lb.get("closed_h4"),
            lb.get("h4_closed"),
            lb.get("h4_klines"),
            lb.get("klines_4h"),
            m.get("closed_h4"),
            m.get("h4_closed"),
            m.get("h4_klines"),
            m.get("klines_4h"),
            x.get("closed_h4"),
            x.get("h4_closed"),
            x.get("h4_klines"),
            x.get("klines_4h"),
        ]

        for arr in candidates:
            if not isinstance(arr, list) or len(arr) < 3:
                continue

            last3 = arr[-3:]
            ranges = []

            for k in last3:
                kh = None
                kl = None

                if isinstance(k, dict):
                    kh = to_float(k.get("high") or k.get("h"))
                    kl = to_float(k.get("low") or k.get("l"))
                elif isinstance(k, (list, tuple)):
                    if len(k) >= 4:
                        kh = to_float(k[2])
                        kl = to_float(k[3])

                if kh is None or kl is None or kh <= kl:
                    ranges = []
                    break

                ranges.append(kh - kl)

            if len(ranges) == 3:
                return sum(ranges) / 3

        return None

    avg_range_3h4 = get_avg_range_3h4()

    if last is None:
        return {
            "available": False,
            "lines": ["- 建议执行：NA（缺少 LBank last / CoinGlass price）"]
        }

    if high is not None and low is not None and high > low:
        range_abs = high - low
    else:
        range_abs = abs(last) * 0.02

    if range_abs <= 0:
        range_abs = abs(last) * 0.02

    lines = []

    if side == "LONG":
        pullback_high = last - 0.10 * range_abs
        pullback_low = last - 0.25 * range_abs

        if pullback_low > pullback_high:
            pullback_low, pullback_high = pullback_high, pullback_low

        breakout_ref = max(high, last * 1.003) if high is not None else last * 1.003
        risk_ref = max(last - 0.40 * range_abs, low) if low is not None else last - 0.40 * range_abs

        lines.extend([
            "建议执行：",
            "- 状态：做多观察，不是正式开仓提醒，当前仓位 0%。",
            "",
            f"- 优先回踩观察区间：{fmt(pullback_low)} - {fmt(pullback_high)}",
            f"  条件：价格先回踩进入该区间；若不跌破 {fmt(pullback_low)}，并在区间内出现止跌/重新走强信号，可考虑区间内低吸观察；跌破 {fmt(pullback_low)} 则不入场。",
            "",
            f"- 回踩确认价：{fmt(pullback_high)} 上方",
            f"  条件：重新站上 {fmt(pullback_high)} 说明回踩确认成功；若已明显拉离 {fmt(pullback_high)}，不追高。",
            "",
            f"- 备选突破入场：{fmt(breakout_ref)} 上方",
            f"  条件：4H 有效站上 {fmt(breakout_ref)} 后，回踩不跌破 {fmt(breakout_ref)} 再考虑；直接拉升不追。",
            "",
        ])

        if avg_range_3h4 is None:
            lines.extend([
                "- 止损建议：最近3根4H区间数据缺失，暂不建议正式开仓。",
                "",
            ])
        else:
            pullback_stop_price = pullback_low - avg_range_3h4
            breakout_stop_price = breakout_ref - avg_range_3h4
            lines.extend([
                "- 止损建议：",
                f"  回踩入场止损：{fmt(pullback_stop_price)}",
                f"  突破入场止损：{fmt(breakout_stop_price)}",
                "",
            ])

        lines.extend([
            "- 失效参考：",
            f"  跌破 {fmt(risk_ref)} 后，当前做多观察失效，重新评估。",
        ])

    elif side == "SHORT":
        retest_low = last + 0.10 * range_abs
        retest_high = last + 0.25 * range_abs

        if retest_low > retest_high:
            retest_low, retest_high = retest_high, retest_low

        breakdown_ref = last * 0.997
        invalid_ref = min(last + 0.40 * range_abs, high) if high is not None else last + 0.40 * range_abs

        lines.extend([
            "建议执行：",
            "- 状态：做空观察，不是正式开仓提醒，当前仓位 0%。",
            "",
            f"- 优先反弹观察区间：{fmt(retest_low)} - {fmt(retest_high)}",
            f"  条件：价格先反弹进入该区间；若不能有效突破 {fmt(retest_high)}，并在区间内出现承压/重新走弱信号，可考虑区间内反弹做空观察；突破 {fmt(retest_high)} 则不入场。",
            "",
            f"- 反弹确认价：{fmt(retest_low)} 下方",
            f"  条件：重新跌回 {fmt(retest_low)} 下方，说明反弹失败确认；若已明显跌离 {fmt(retest_low)}，不追空。",
            "",
            f"- 备选跌破入场：{fmt(breakdown_ref)} 下方",
            f"  条件：4H 有效跌破 {fmt(breakdown_ref)} 后，反抽不重新站回 {fmt(breakdown_ref)} 上方再考虑；直接下杀不追。",
            "",
        ])

        if avg_range_3h4 is None:
            lines.extend([
                "- 止损建议：最近3根4H区间数据缺失，暂不建议正式开仓。",
                "",
            ])
        else:
            rebound_stop_price = retest_high + avg_range_3h4
            breakdown_stop_price = breakdown_ref + avg_range_3h4
            lines.extend([
                "- 止损建议：",
                f"  反弹入场止损：{fmt(rebound_stop_price)}",
                f"  跌破入场止损：{fmt(breakdown_stop_price)}",
                "",
            ])

        lines.extend([
            "- 失效参考：",
            f"  突破 {fmt(invalid_ref)} 后，当前做空观察失效，重新评估。",
        ])

    else:
        lines.append("建议执行：NA（未知方向）")

    return {
        "available": True,
        "last": last,
        "high": high,
        "low": low,
        "open": open_price,
        "range_abs": range_abs,
        "avg_range_3h4": avg_range_3h4,
        "lines": lines,
    }
```


## 13. Claude Code / 新 Agent 迁移说明

迁移到 Claude Code 或新 Agent 时，建议文件结构：

- ./skills/V7_LONG_SKILL.md
- ./skills/MEME_BIDIR_SKILL.md

Claude Code 项目说明中必须写：

- BTC/ETH 稳健做多分析，遵守 V7_LONG_SKILL.md
- memecoin / 高波动山寨双向观察，遵守 MEME_BIDIR_SKILL.md
- 两套策略相互独立
- 任何报告必须明确策略名称
- 任何 MEME-BIDIR 报告必须明确“观察，不是正式开仓提醒，当前仓位0%”
- 不得把任一策略的回测结果迁移给另一策略

MEME-BIDIR 当前最重要的迁移规则：

- 止损建议必须给具体价格
- 如果最近3根4H区间数据缺失，必须提示暂不建议正式开仓
- 入场观察区间和确认价必须拆开表达
- 不得让用户误解为“必须突破区间上沿才算区间入场”

---

## 14. 纸账户第一周复盘与优化记录（2026-07-05）

本节为 claude-trading-bot-v1 模拟盘（paper_bot，LBank 4h，初始 2000 USDT）第一周 forward-test 复盘结论。模拟盘是 MEME 突破策略的前向验证载体，其规则改动必须同步记录在本 skill 中。

### 14.1 复盘数据（2026-06-27 至 2026-07-05）

- 已平仓 31 笔：胜率 38.7%，Profit Factor 0.64，已实现 -101.18 USDT，净值 -5.93%
- 做多 22 笔：胜率 45%，+36.61 USDT，PF 1.32（框架有效）
- 做空 9 笔：胜率 22%，-137.79 USDT，PF 0.17（全部亏损来源）
- 最大单笔：UDOGE 空单 -113.79 USDT（-116%），微盘币被拉超 2 倍，止损从未被硬执行
- 主要假突破亏损：USELESS 两笔合计 -44 USDT、GORK -28.8 USDT，均为缩量突破后立即反转

### 14.2 本次确认的三条新硬规则（已同步 claude-trading-bot-v1 代码）

1. 硬止损与熔断（paper_bot.py）：每次运行必须将最新价与仓位存储的止损价直接比较，触发立即平仓，不得等待 4h 状态机翻转；任一仓位浮亏达到开仓名义值 15% 时强制熔断平仓；强平后同一次运行内不得重新开仓。
2. 微盘币剥除（exchange_data.py）：udoge、shibdoge、caw、manyu、babyshark、kekius 移出监控池。恢复任一币种前必须单独做流动性评估。
3. 突破成交量确认（strategy_core.py）：突破/跌破那根 4h K 线的成交量必须 > 最近 20 根 K 线平均成交量的 1.2 倍，否则不入场；做多做空同用。

### 14.3 观察中事项（未定，禁止提前当作结论）

- EMA 趋势过滤线参数：当前保持 EMA100。已新增 backtest_regime.py + backtest.yml（每周日 02:00 UTC 自动跑 + 可手动触发），用 LBank 4h 历史对比 EMA55 与 EMA100 的胜率 / PF / 累计收益。只有连续数周 EMA55 明显占优才允许切换，切换需再次人工确认。
- 做空功能保留（用户决定），但必须受硬止损 + 15% 熔断 + 微盘剥除约束。做空绩效继续单独跟踪，若下周复盘仍显著为负，重新评估是否停用。

### 14.4 纪律边界不变

- 本节记录的是模拟盘 forward-test 规则，不改变本 skill 第 1-13 节的观察纪律：MEME-BIDIR 对真实账户仍然只做观察 / 预警，不发正式开仓提醒，当前仓位 0%。
- 模拟盘绩效不得当作实盘绩效宣称，也不得迁移给 V7 或 HR-SHORT。

---

## 15. 11 个月深度回测与参数上线记录（2026-07-05）

同日完成的深度回测（claude-trading-bot-v1 → backtest_deep.py，LBank 4h × 2000 根 ≈ 11 个月，2025-08-06 至 2026-07-05，BTC/ETH trend + 9 山寨 breakout，含手续费滑点）。

### 15.1 关键结论

- 全窗口基线：388 笔，胜率 32.7%，PF 1.29，+227.1%——策略长期有效；近 3 个月亏损是震荡期问题（Q3 PF 0.34），非结构性失效。
- 亏损归因三发现：
  1. 持仓 ≤1 天的交易胜率 12.3%（-187%），持仓 >3 天的胜率 89.7%（+389.7%）——速死交易是最大漏点
  2. EMA 穿线出场胜率 4.3%（PF 0.01），移动止损出场 PF 1.85——但"仅止损出场"变体验证无增益，出场逻辑维持不变
  3. 11 个月里做空 PF 1.71（+279%）、做多 PF 0.86（-51.9%）——做空必须保留，第一周纸账户的做空亏损是风控失败而非信号失败
- 参数敏感性 18 个配置中，唯一前后半段都盈利的组合：**breakout=55 + rsi_max=65**（FULL PF 1.65 / +250%，近半年 PF 1.13 / +20.4%，基线近半年为 -127%）。

### 15.2 已上线参数变更（2026-07-05，用户确认）

- breakout（Donchian 突破窗口）：20 → **55**（约 9 天）
- rsi_max（突破做多 RSI 上限）：75 → **65**
- 其余不变：EMA regime 100、stop_mult 2.5、vol_mult 1.2、双向交易、硬止损 + 15% 熔断

### 15.3 监控要求

- 每周日 regime-backtest workflow 持续验证；纸账户下周复盘重点看新参数下的交易频率（预期显著下降）与质量
- 单窗口验证的局限已知悉：前后半段一致性是当前最强证据，但不构成未来保证；若连续两周实盘表现与回测严重背离，回滚参数并重新归因

# Initial Long Strategy V2 / V7 高胜率过滤版

## 1. 策略定位

本策略用于 BTC / ETH 的低杠杆短线至波段做多判断。

策略方向：
- 只做多
- 不做空
- 做空默认仅观察，仓位 0%

策略状态：
- 正式执行版本
- 当前用于 market-analyst-v2 agent
- 可复制安装到新 agent
- 核心开仓策略仍为 V7 高胜率过滤版
- 新增 V7-T 趋势尾仓 / 二次回踩观察模块，用于减少固定 1.5R 止盈后错过大趋势的情况

验证状态：
- V7 核心回测基于约 180 天 CoinGlass 4h 资金流数据验证
- 不能宣称已经通过完整 365 天资金流验证
- 365 天价格数据可用，但 CoinGlass 4h OI / Funding / Liquidation 当前仅返回约 1080 根，约等于 180 天
- 当前回测结果只对应“完整 V7 开仓 + 固定 1.5R 止盈”的核心版本
- V7-T 趋势尾仓 / 二次回踩观察模块属于新增实盘辅助规则，未纳入原回测结果，不能直接套用原胜率、Profit Factor 或 total_r 结论

## 2. 回测结果

V7 在当前可用资金流数据内：

- 交易次数：21
- 胜率：71.43%
- total_r：+14.4116
- Profit Factor：3.2078
- 最大回撤：-1.1647R
- 最大连续亏损：1
- 平均持仓：6.76 小时

BTC_LONG：
- 交易次数：11
- 胜率：72.73%
- total_r：+7.6989
- Profit Factor：3.3627

ETH_LONG：
- 交易次数：10
- 胜率：70.00%
- total_r：+6.7126
- Profit Factor：3.0533

重要说明：
- 以上回测数据只代表 V7 核心版本
- 以上回测数据不代表 V7-T 趋势尾仓模块
- 如果未来启用尾仓或二次回踩再入，必须单独回测，不能直接宣称优于原版

## 3. 数据源

LBank：
- H1 / H4 / D1 OHLC
- EMA5 / EMA10 / EMA21 / EMA55 / EMA200
- RSI14
- ATR14
- recent20 high / low
- recent55 high / low
- volume_ratio_vs_20

CoinGlass：
- 4h OI
- 4h Funding
- 4h Long Liquidation
- 4h Short Liquidation

CoinGecko：
- 当前价格
- 24h 涨跌
- 24h 成交量
- 市值

注意：
- OHLC / ATR14 / EMA / RSI / 支撑压力必须优先使用 LBank
- CoinGecko OHLC 429 不影响本策略执行
- CoinGlass 1h 资金流不是本策略必要条件

## 4. V7 资金面条件

做多必须同时满足以下三项。

### 4.1 Funding 条件

Funding 必须满足以下任一条件：

1. Funding < -0.10%
2. 0.05% <= Funding < 0.10%

示例：
- Funding = -0.2533%，通过
- Funding = -0.2845%，通过
- Funding = -0.05%，不通过
- Funding = 0.12%，不通过
- Funding = 0.20%，不通过

旧规则已废弃：
- 禁止继续使用 Funding 在 -0.15% 到 0.12% 之间

### 4.2 OI 条件

4h OI change_pct 必须满足：

-1.0% < 4h OI change_pct < 1.0%

含义：
- OI 没有快速上升
- OI 没有快速下降
- 杠杆资金相对稳定

### 4.3 Liquidation 禁止追多条件

如果同时满足以下两项，则禁止追多：

- short_liq > long_liq × 4
- short_liq > 1,000,000 USD

如果触发禁止追多：
- 当前仓位必须为 0%
- 只能观察，不能给开仓建议

## 5. 技术面条件

### 5.1 H1 执行层

做多需要满足：

- H1 价格回踩 EMA10 / EMA21 附近
- H1 收盘价重新站上 EMA10 和 EMA21
- 前一根 H1 曾经在 EMA10 或 EMA21 下方
- H1 RSI14 必须满足：45 <= RSI14 <= 72
- 当前价格距离 H1 EMA21 不得超过 1.5 × H1 ATR14
- volume_ratio_vs_20 >= 0.5

### 5.2 H4 过滤层

必须满足：

- H4 收盘价高于 H4 EMA21
- H4 RSI14 < 78

### 5.3 D1 风险层

必须满足：

- D1 RSI14 > 22

## 6. 开仓确认

只允许在 H1 收盘后判断。

禁止：
- 盘中触碰就开仓
- 技术面未通过但资金面通过就开仓
- 资金面未通过但技术面通过就开仓
- 做空开仓

做多必须同时满足：
- 技术面通过
- Funding 通过
- 4h OI change_pct 通过
- Liquidation 禁止追多未触发

## 7. 止损、止盈、R 定义与仓位换算

### 7.1 先用市场波动决定止损

V7 的止损必须优先由市场结构和波动决定，而不是先由本金百分比决定。

做多止损：

max(
  H1 recent20_low - 0.2 × H1 ATR14,
  开仓价 - 1.5 × H1 ATR14
)

含义：
- H1 recent20_low 代表最近 20 根 H1 的结构低点
- 0.2 × ATR14 是给结构低点预留的正常波动缓冲
- 开仓价 - 1.5 × ATR14 是最大波动止损距离约束，避免止损过远导致单笔风险失控
- 因此，止损不是固定百分比，而是随 ATR 和近期结构变化动态调整

### 7.2 R 定义

R 是单笔交易的“风险单位”。

做多时：
- R = 开仓价 - 止损价
- 如果开仓价是 100，止损价是 98，则 1R = 2 美元价格风险
- R 不是收益率，也不是本金百分比
- R 先由止损距离决定，再换算为实际仓位和美元风险

核心 V7 止盈：
- 回测版本使用固定 1.5R 止盈
- 止盈价 = 开仓价 + 1.5 × R
- 原回测结果仅适用于这个固定 1.5R 止盈版本

### 7.3 仓位应由“止损距离 + 账户风险上限”反推

V7 不应使用固定开仓百分比作为唯一仓位依据。

推荐流程：
1. 先按 ATR / recent20_low 计算止损价
2. 再计算 R 和止损百分比
3. 再按账户允许的单笔最大亏损，反推出本次开仓金额

计算公式：
- 止损百分比 = (开仓价 - 止损价) / 开仓价
- 单笔允许亏损金额 = 账户本金 × 单笔风险比例
- 开仓名义金额 = 单笔允许亏损金额 / 止损百分比

默认风险档位：
- 保守：每笔最大亏损 0.5% 本金
- 标准：每笔最大亏损 1.0% 本金
- 激进：每笔最大亏损 1.5% - 2.0% 本金

如果计算出的开仓名义金额过大，应降低风险档位或放弃交易，不应为了凑仓位而扩大止损。

### 7.4 示例

本金 10,000 USD，单笔风险 1%，则本次最多允许亏损 100 USD。

如果 BTC 开仓价 100,000，按 ATR / recent20_low 算出的止损价是 98,500：
- R = 1,500
- 止损百分比 = 1.5%
- 开仓名义金额 = 100 / 1.5% = 6,666.67 USD
- 到止损亏损约 100 USD
- 到 1.5R 止盈盈利约 150 USD

如果止损距离变成 3.0%，则：
- 开仓名义金额 = 100 / 3.0% = 3,333.33 USD
- 到止损仍然亏损约 100 USD
- 到 1.5R 止盈仍然盈利约 150 USD

因此，V7 的合理仓位不是固定 20% 或 30%，而是随着 ATR 止损距离动态变化。

## 8. V7-T 趋势尾仓 / 二次回踩观察模块

### 8.1 模块定位

V7-T 不是独立开仓策略。

V7-T 的作用：
- 在 V7 已经触发并达到 1.5R 后，判断是否可以用小比例尾仓尝试吃更大的趋势延伸
- 在 V7 固定止盈后，继续观察 BTC / ETH 是否出现新的二次回踩再入机会
- 解决 V7 平均持仓时间较短、可能错过趋势上涨空间的问题

V7-T 的限制：
- 不改变 V7 原始开仓条件
- 不允许在 V7 条件未通过时给非 0% 新开仓建议
- 不允许把 V7-T 的观察状态写成正式开仓信号
- 不允许把原 V7 回测胜率、Profit Factor、total_r 直接套用到 V7-T

### 8.2 趋势尾仓规则

当完整 V7 开仓已经达到 1.5R 后，可以考虑：

- 70% - 80% 主仓按原计划在 1.5R 止盈
- 20% - 30% 小比例尾仓进入趋势延伸观察
- 尾仓止损必须至少上移到开仓价附近，原则上不能让已盈利交易重新变成亏损交易

趋势尾仓继续持有的参考条件：
- H1 收盘价仍在 H1 EMA21 上方
- H4 收盘价仍在 H4 EMA21 上方
- H4 RSI14 < 78
- Funding 未进入明显过热状态
- 4h OI change_pct 未出现快速上升或快速下降
- Liquidation 禁止追多条件未触发

趋势尾仓退出条件，满足任一项应提示退出或收紧止损：
- H1 收盘价有效跌破 H1 EMA21
- H4 收盘价跌破 H4 EMA21
- H4 RSI14 >= 78
- Funding >= 0.10%
- 4h OI change_pct >= 1.0% 或 <= -1.0%
- short_liq > long_liq × 4 且 short_liq > 1,000,000 USD

### 8.3 二次回踩再入规则

如果 V7 已经固定止盈，后续 BTC / ETH 继续保持多头结构，可以观察二次回踩机会。

二次回踩再入必须重新满足完整 V7 开多条件：
- H1 价格回踩 EMA10 / EMA21 附近
- H1 收盘价重新站上 EMA10 和 EMA21
- 前一根 H1 曾经在 EMA10 或 EMA21 下方
- H1 RSI14 满足 45 <= RSI14 <= 72
- 当前价格距离 H1 EMA21 不超过 1.5 × H1 ATR14
- volume_ratio_vs_20 >= 0.5
- H4 收盘价高于 H4 EMA21
- H4 RSI14 < 78
- D1 RSI14 > 22
- Funding 通过 V7 条件
- 4h OI change_pct 通过 V7 条件
- Liquidation 禁止追多未触发

如果二次回踩只满足部分条件：
- 当前仓位：0%
- 只能写观察区、触发价、触发后计划仓位
- 不发送正式开仓提醒

## 9. V7-L 杠杆风控层：10x-20x 合约执行规则

### 模块定位

V7-L 不是新的开仓策略，不改变 V7 技术面、资金面、止盈止损和 V7-T 趋势尾仓规则。

V7-L 只用于在合约杠杆环境下，把 V7 的止损距离、R 值、账户风险上限、名义仓位、实际保证金占用和爆仓风险统一计算清楚。

### 核心原则

1. 杠杆倍数不改变 V7 入场信号。
2. 杠杆倍数不改变 ATR / recent20_low 算出的止损价。
3. 杠杆倍数不改变 R 的定义。
4. 杠杆倍数只影响需要占用多少保证金，以及爆仓价距离开仓价有多近。
5. 不允许因为开了 10x 或 20x，就把名义仓位直接放大到本金的 10 倍或 20 倍。
6. V7 实盘必须优先控制“账户单笔最大亏损”，而不是优先追求高杠杆仓位。

### 推荐执行模式

V7 合约执行时必须先计算：

- 开仓价
- 止损价
- R = 开仓价 - 止损价
- 止损百分比 = R / 开仓价
- 账户本金
- 单笔允许亏损金额 = 账户本金 × 单笔风险比例
- 开仓名义金额 = 单笔允许亏损金额 / 止损百分比
- 实际占用保证金 = 开仓名义金额 / 杠杆倍数
- 有效账户杠杆 = 开仓名义金额 / 账户本金

### 10x-20x 风险档位

如果用户计划使用 10x-20x 杠杆，建议将默认单笔风险下调：

- 保守：每笔最大亏损 0.25% - 0.5% 本金
- 标准：每笔最大亏损 0.5% 本金
- 激进：每笔最大亏损 1.0% 本金
- 不建议在 10x-20x 下默认使用 1.5% - 2.0% 单笔风险

原因：高杠杆会放大爆仓风险、滑点风险、止损未成交风险、资金费率风险和连续亏损后的恢复难度。

### 名义仓位与保证金示例

账户本金 10,000 USD，BTC 开仓价 100,000，止损价 98,500：

- R = 1,500
- 止损百分比 = 1.5%

如果单笔风险为 0.5%：
- 单笔允许亏损 = 50 USD
- 开仓名义金额 = 50 / 1.5% = 3,333.33 USD
- 10x 占用保证金 ≈ 333.33 USD
- 20x 占用保证金 ≈ 166.67 USD
- 有效账户杠杆 = 3,333.33 / 10,000 = 0.33x

如果单笔风险为 1.0%：
- 单笔允许亏损 = 100 USD
- 开仓名义金额 = 100 / 1.5% = 6,666.67 USD
- 10x 占用保证金 ≈ 666.67 USD
- 20x 占用保证金 ≈ 333.33 USD
- 有效账户杠杆 = 6,666.67 / 10,000 = 0.67x

注意：即使交易所杠杆设置为 20x，也不代表必须开到账户本金 20 倍的名义仓位。V7 应以风险金额反推名义仓位。

### 禁止的错误用法

账户本金 10,000 USD，如果直接用 10x 开满：
- 名义仓位 = 100,000 USD
- 如果止损距离 1.5%，止损亏损 ≈ 1,500 USD
- 等于本金 -15%

如果直接用 20x 开满：
- 名义仓位 = 200,000 USD
- 如果止损距离 1.5%，止损亏损 ≈ 3,000 USD
- 等于本金 -30%

这不符合 V7 的稳健定位，必须禁止。

### 强制风控要求

使用 10x-20x 时，V7 报告必须额外输出：

- 杠杆倍数
- 开仓名义金额
- 实际占用保证金
- 有效账户杠杆
- 止损触发时预计亏损 USD
- 止损触发时亏损占本金百分比
- 1.5R 止盈时预计盈利 USD
- 是否建议使用逐仓
- 是否存在爆仓价早于止损价的风险

原则：止损价必须明显早于爆仓价。若爆仓价距离开仓价过近，必须降低名义仓位、降低杠杆或放弃交易。

### 保证金模式建议

V7 默认建议逐仓，而不是全仓。

原因：
- 逐仓可以把单笔风险限制在该仓位保证金和预设止损范围内
- 全仓可能让账户其他资金被动参与抗亏损，扩大单笔失控风险

如果使用全仓，报告必须明确提示：全仓下单笔风险可能扩散到账户整体，不符合 V7 默认稳健执行风格。

### 对原回测结论的限制

V7 原回测的 total_r、胜率、Profit Factor 只代表策略信号和 1.5R 止盈止损结构的历史表现。

如果实盘使用 10x-20x 杠杆：
- 不能直接宣称回测收益率等于实盘收益率
- 必须按实际止损距离、名义仓位、手续费、滑点、资金费率和爆仓风险重新换算
- 若使用不同于回测的仓位、杠杆、止损执行方式，需要单独记录实盘绩效

## 10. 仓位纪律

如果未触发：
- 当前仓位：0%
- 只能写观察区、触发价、触发后计划仓位

如果技术面不通过：
- 当前仓位：0%

如果资金面不通过：
- 当前仓位：0%

如果做空：
- 当前仓位：0%

只有技术面和资金面同时通过，才允许给非 0% 新开仓仓位。

趋势尾仓纪律：
- 趋势尾仓只允许来自已经达到 1.5R 的 V7 原始持仓
- 趋势尾仓不是新增追多仓位
- 如果没有前序 V7 持仓记录，不得凭 V7-T 单独给尾仓建议
- 如果只是 V7-T 观察，当前新开仓仓位仍为 0%

## 11. Telegram 提醒条件

V7 条件提醒监控器应每小时检测一次，建议在每小时第 10 分钟运行。

只有满足完整 V7 开多条件时才发送 Telegram 开仓提醒。

提醒必须包含：
- 触发币种
- 当前执行策略
- 当前价格
- 触发方向：做多
- 观察区或触发价
- 止损
- 止盈
- R 值说明
- 建议仓位
- Funding 数值与是否通过
- 4h OI change_pct 数值与是否通过
- short_liq
- long_liq
- short_liq / long_liq
- 触发原因
- 风险提示
- V7-T 趋势尾仓状态：未适用 / 可观察 / 应收紧 / 应退出

如果只是观察、当前仓位 0%、技术面未触发、资金面未通过，不发送正式开仓提醒。

V7-T 提醒规则：
- 如果系统无法追踪历史持仓是否已经达到 1.5R，不发送尾仓管理提醒，只在报告中写观察状态
- 如果系统能追踪到 V7 持仓已经达到 1.5R，可发送“尾仓管理提醒”，但不得写成新的开仓提醒
- 二次回踩只有在重新满足完整 V7 开多条件时，才可以作为新的 V7 开仓提醒

## 12. 报告输出要求

每次 BTC / ETH 交易建议中必须写：

- 当前执行策略：初始做多策略 V2 / V7 高胜率过滤版
- Funding = X%，V7 允许区间：Funding < -0.10% 或 0.05% <= Funding < 0.10%，通过/不通过
- 4h OI change_pct = X%，V7 阈值：-1.0% < OI < 1.0%，通过/不通过
- short_liq = X USD
- long_liq = Y USD
- short_liq / long_liq = Z
- 禁止追多阈值：short_liq > long_liq × 4 且 short_liq > 1,000,000 USD，触发/未触发
- 技术面是否通过
- 资金面是否通过
- 当前仓位
- R 值：开仓价 - 止损价
- 止损百分比：(开仓价 - 止损价) / 开仓价
- 单笔风险档位：
  - 非高杠杆默认：保守 0.5% / 标准 1.0% / 激进 1.5%-2.0%
  - 10x-20x 模式：保守 0.25%-0.5% / 标准 0.5% / 激进最高 1.0%
- 按风险档位反推的建议开仓名义金额
- 杠杆倍数：如 10x / 20x
- 实际占用保证金：开仓名义金额 / 杠杆倍数
- 有效账户杠杆：开仓名义金额 / 账户本金
- 止损触发时预计亏损 USD 与占本金比例
- 1.5R 止盈时预计盈利 USD
- 爆仓价是否早于止损价：是 / 否 / 无法确认
- 固定止盈：1.5R
- V7-T 趋势尾仓状态：未适用 / 可观察 / 应收紧 / 应退出
- 是否存在二次回踩再入机会：是 / 否 / 仅观察

当用户询问回测指标时必须说明：
- R 是单笔交易风险单位，不是本金百分比
- total_r 是所有交易按 R 标准化后的累计收益
- Profit Factor = 总盈利 / 总亏损
- Profit Factor 不是本金收益率，也不是百分比

## 13. 新 agent 安装说明

把本文件内容追加到新 agent 的 AGENTS.md 或 SOUL.md 中。

推荐安装位置：

/home/ubuntu/.openclaw/agents/<agent_id>/workspace/AGENTS.md

安装命令示例：

cat /home/ubuntu/.openclaw/skills/initial_long_strategy_v2_v7/SKILL.md >> /home/ubuntu/.openclaw/agents/<agent_id>/workspace/AGENTS.md

安装后必须重启 gateway：

systemctl --user restart openclaw-gateway.service

## 14. 重要限制

本策略不是盈利保证。

当前回测基于历史数据和当前可用数据源，未来市场结构、交易所流动性、资金费率机制、数据 API 可用性变化，都可能导致策略失效。

实盘执行时必须控制仓位，默认低杠杆。若用户明确使用 10x-20x 杠杆，必须启用 V7-L 杠杆风控层，并默认下调单笔账户风险。仓位应优先按 ATR / recent20_low 计算止损距离，再按账户单笔风险上限反推，不应只按固定本金百分比或交易所最高杠杆开仓。

V7-T 趋势尾仓 / 二次回踩观察模块是新增辅助规则，必须经过单独回测后，才能作为正式绩效结论使用。
V7-L 杠杆风控层用于 10x-20x 合约执行时的仓位和保证金换算。杠杆倍数不得改变 V7 入场条件、止损价格和 R 定义；使用高杠杆时必须优先控制账户单笔最大亏损和爆仓价相对止损价的位置。

## 15. V7-P LBank 纸面账户与 Telegram 推送

### 15.1 模块定位

V7-P 是 V7 做多策略的纸面账户监控模块。

用途：
- 持续测试 V7 做多方向是否能稳定运行
- 每天生成 LBank 做多策略信号
- 次日早上 08:00 复盘前一日表现
- 维护 2000 USDT 纸面账户的 30 日滚动损益
- 通过 Telegram bot 青铜c 推送信号和复盘

边界：
- V7-P 只做多
- V7-P 不做空
- 做空模块后续单独开发
- V7-P 的 30 日纸面账户结果不得替代 V7 原始回测结论
- 如果没有 Telegram token / chat id，不得假装已经推送成功

### 15.2 当前本地实现文件

仓库文件：

`config/lbank_paper.json`

`scripts/lbank_paper_trader.py`

`docs/LBANK_PAPER_WORKFLOW.md`

当前纸面账户结果：

`results/lbank_paper/simulation_30d_summary.json`

### 15.3 当前 30 日纸面账户基线

当前 LBank 现货日线 30 日模拟：

- 区间：2026-06-05 至 2026-07-04
- 初始资金：2000 USDT
- 当前权益：2000 USDT
- 盈亏：0 USDT
- 收益率：0.00%
- 交易数：0
- 当前仓位：空仓

解释：
- 最近 30 天没有触发 V7-P 做多目标仓位
- 结果应解释为策略空仓等待，不是亏损，也不是脚本未运行

### 15.4 LBank 数据与资金费率

V7-P 当前使用 LBank 现货日线：

`/v2/kline.do`

合约资金费率预期来自 LBank futures marketData 的 `prePositionFeeRate` 字段。

如果当前环境访问 LBank 合约公开行情返回 403：
- 报告必须写明资金费率暂不可用
- 纸面账户暂按 0 资金费率计算
- 实盘前必须解决合约 API 可访问性、symbol 映射、资金费率结算时间和手续费档位

### 15.5 Telegram 推送纪律

Telegram 使用本地 `.env`：

`TELEGRAM_BOT_TOKEN`

`TELEGRAM_CHAT_ID`

纪律：
- token 和 chat id 不得写入仓库
- `.env` 不得提交到 GitHub
- 缺少 Telegram 配置时，只允许本地打印，不得声称已经发给用户
- 如旧的青铜c每日内容来自其他 crontab、OpenClaw、服务器或 Telegram 端自动化，必须到原系统停用；不得在无法定位来源时误删其他任务

### 15.6 定时任务建议

建议任务：

- 每日信号：每天收盘后运行 `python3 scripts/lbank_paper_trader.py signal`
- 前一日复盘：每天 08:00 运行 `python3 scripts/lbank_paper_trader.py review`

如果使用 Codex automation：
- `lbank-crypto-long-only-daily-signal`
- `lbank-crypto-paper-account-morning-review`

如果 Telegram 配置未完成，自动任务应保持暂停。


## 加密货币三组策略分工总览

当前加密货币交易系统分为三组策略 / 模块，三者必须严格区分，不得混用绩效、触发条件或 Telegram 提醒类型。

### 1. V7 稳健做多策略

路径：

/home/ubuntu/.openclaw/skills/initial_long_strategy_v2_v7

定位：

- 正式生产策略
- 只做 BTC / ETH
- 只做多
- 不做空
- 技术面 + Funding + OI + 清算过滤同时通过，才允许非 0% 仓位

Telegram 规则：

- V7 条件提醒监控：每小时第 10 分钟检测一次
- 市场报告：每 4 小时一次，从北京时间 08:30 开始
- 只有 BTC / ETH 满足完整 V7 开多条件，才发送正式开仓提醒
- 如果只是观察、技术面不通过、资金面不通过、当前仓位 0%，不发送开仓提醒

仓位规则：

- V7 允许在完整条件满足时给出非 0% 仓位
- 仓位必须基于 ATR / 结构止损和账户风险反推
- 杠杆只影响保证金，不改变入场信号、止损、R 定义

### 2. HR-SHORT 高风险做空策略

路径：

/home/ubuntu/.openclaw/skills/high_risk_short_strategy_v1

定位：

- 高风险做空研究策略
- 主要用于高波动山寨 / memecoin 的做空观察
- 当前状态为回测候选 / 观察，不是正式生产开仓策略

已知回测候选：

- score3_aggressive + NEIRO
- score3_aggressive + PEOPLE
- score4_balanced + ACT
- score4_balanced + SHIB

Telegram 规则：

- 只能发送观察 / 预警
- 不允许发送正式做空开仓提醒
- 当前仓位必须为 0%
- 是否有定时任务，以服务器 crontab 实际配置为准
- 不得把 HR-SHORT V1E 的固定币种回测绩效套用到新币或动态池

限制：

- 新币可以进入动态观察池
- 新币不能共享固定核心池回测绩效
- 新币只有在独立回测 / 严格验证后，才可以升级为正式提醒候选

### 3. MEME-BIDIR 双向高波动策略

路径：

/home/ubuntu/.openclaw/skills/high_risk_short_strategy_v1

定位：

- 高波动山寨 / memecoin 双向 live 观察模块
- 同时研究做多和做空
- 独立于 V7，也独立于 HR-SHORT V1E
- 当前只允许 live 观察 / 预警，不允许正式开仓

当前脚本：

/home/ubuntu/.openclaw/tools/meme_bidir_live_observe_watch.py

数据源：

- CoinGlass spot/futures pairs-markets：用于 live 短周期强势观察
- CoinGlass futures price/history 4h：用于 4h 回测研究
- LBank futures SwapU marketData：用于实盘 live 校验

Telegram 规则：

- 当前定时任务建议每小时第 25 分钟运行一次
- 与 V7 每小时第 10 分钟监控错开
- 建议使用 --side both 同时观察做多和做空
- 只发送 live 观察 / 预警
- 不发送正式开仓
- 当前仓位固定为 0%

MEME-BIDIR 做多观察：

- 用于发现新币 / 高波动币初始拉升、放量、资金流增强
- 推送中可以包含建议入场参考、突破确认参考价、回踩观察区、风险失效参考
- 这些价格只是观察参考，不是正式开仓价

MEME-BIDIR 做空观察：

- 不是“涨了就空”
- 必须观察是否出现大幅拉升、高位回落、振幅扩大、Funding 偏正、成交额足够等条件
- 做空观察不等于正式做空开仓

重要限制：

- MEME-BIDIR 做多不得引用 V7 回测绩效
- MEME-BIDIR 做空不得引用 HR-SHORT V1E 回测绩效
- live-only / 动态池币种不能引用 4h 回测绩效
- 使用 high/low、短周期强势启动、pairs-markets live 数据的正式开仓规则，必须单独回测
- 正式开仓前必须额外计算 ATR / 结构止损、1.5R 止盈、名义仓位、保证金和爆仓价风险

### 总原则

- V7：正式 BTC/ETH 稳健做多策略
- HR-SHORT：高风险做空观察 / 回测候选
- MEME-BIDIR：高波动币双向 live 观察 / 预警

只有 V7 当前允许在完整条件满足时发送正式开仓提醒。

HR-SHORT 和 MEME-BIDIR 当前都只能发送观察 / 预警，默认仓位 0%，不得自动升级为正式开仓信号。

<!-- V7_ULTRA_COMPACT_MARKET_SUMMARY_START -->
## 市场摘要极简硬规则

当用户要求“市场摘要 / 每日摘要 / 每4小时报告 / BTC ETH 市场报告”时：

1. 必须读取并遵守文件：
/home/ubuntu/.openclaw/agents/market-analyst-v2/workspace/templates/v7_market_summary_ultra_compact.md

2. 只输出 BTC 和 ETH。
3. 不得输出 Memecoin、MEME-BIDIR、HR-SHORT，除非用户明确要求。
4. 不得输出“今日重点 / 风险提示 / 机会窗口 / 交易建议 / 市场判断”五大长段。
5. 不得输出完整交易明细、逐字段诊断、长解释。
6. 每个币最多 9 行，总体尽量控制在手机一屏。
7. V7 未完整通过时，仓位必须 0%。
<!-- V7_ULTRA_COMPACT_MARKET_SUMMARY_END -->

---

## 14. V7 Telegram 市场摘要输出规则

本节用于固化 V7 Telegram 市场摘要 / 每4小时报告 / BTC ETH 市场报告的输出纪律。

这些规则来自当前 OpenClaw market-analyst-v2 已修复版本，用于避免换服务器、换模型或迁移到 Claude Code 后再次出现以下问题：

- Funding / OI / 清算明明有数据，却输出“缺失”
- Funding 单位误判
- -0.0011% Funding 被误判为 V7 通过
- OI 4h 明明有 CoinGlass 变动百分比，却输出“币种级缺失”
- 市场摘要结尾回显测试指令


<!-- V7_MARKET_SUMMARY_DATA_FIX_FULL_BEGIN -->

## V7 市场摘要资金面字段读取强制规则

适用场景：

- 用户要求“市场摘要”
- 用户要求“每日摘要”
- 用户要求“每4小时报告”
- 用户要求“BTC/ETH 市场报告”
- 使用 v7_market_summary_ultra_compact.md
- 使用 v7_market_summary_compact.md

### 1. 禁止错误输出“缺失”

如果输入上下文、工具返回、上游报告或 agent 原始分析中已经出现以下任意字段，不得在市场摘要中写“缺失”：

- Funding
- Funding raw
- CoinGlass Funding
- OI
- OI 4h
- OI change_pct
- CoinGlass 4h OI
- Long liquidation
- Short liquidation
- long_liq
- short_liq
- liquidation
- Liquidation 已提供

错误示例，禁止输出：

- Funding：缺失；OI 4h：缺失
- 清算：Long 缺失 / Short 缺失

如果原始数据中有数值，必须提取并输出数值。

### 2. Funding 输出规则

如果原始数据存在 Funding 数值，市场摘要必须输出：

Funding：{funding_value}，V7 {通过/不通过}

V7 Funding 允许区间：

- Funding < -0.10%
- 或 0.05% <= Funding < 0.10%

如果 Funding 不在允许区间，必须写“不通过”，但不得写“缺失”。

### 3. OI 输出规则

如果原始数据存在 OI 4h 或 OI change_pct，市场摘要必须输出：

OI 4h：{oi_change_pct}，V7 {通过/不通过}

V7 OI 阈值：

- -1.0% < OI change_pct < 1.0%

如果 OI 不在允许区间，必须写“不通过”，但不得写“缺失”。

### 4. 清算输出规则

如果原始数据存在 long_liq / short_liq，市场摘要必须输出：

清算：Long {long_liq} / Short {short_liq}

如果可以计算 short_liq / long_liq，必须进一步判断禁止追多条件：

- short_liq > long_liq × 4
- 且 short_liq > 1,000,000 USD

如果触发，写：

清算：Long {long_liq} / Short {short_liq}，触发禁止追多

如果未触发，写：

清算：Long {long_liq} / Short {short_liq}，未触发禁止追多

### 5. 真正缺失时的输出

只有当原始数据、工具返回、上游报告中完全没有对应字段时，才允许写“缺失”。

如果只是 V7 不通过，必须写“不通过”，不能写“缺失”。

正确示例：

- Funding：0.005301%，V7 不通过
- OI 4h：0.0956%，V7 通过
- 清算：Long 5975.19 USD / Short 673452.92 USD，未触发禁止追多

错误示例：

- Funding：缺失；OI 4h：缺失
- 清算：Long 缺失 / Short 缺失

### 6. 市场摘要最小资金面格式

每个 BTC / ETH 小节必须尽量使用以下格式：

- Funding：{funding_value}，V7 {通过/不通过}
- OI 4h：{oi_change_pct}，V7 {通过/不通过}
- 清算：Long {long_liq} / Short {short_liq}，禁止追多 {触发/未触发}

如果确实缺失，才写：

- Funding：缺失
- OI 4h：缺失
- 清算：缺失

### 7. 结论判断规则

市场摘要结论必须区分“不通过”和“缺失”。

如果 Funding / OI / 清算有数据但不满足 V7，结论应写：

- 资金面不通过
- V7 未完整通过
- 当前仓位 0%

不得写：

- 资金面缺失
- Funding 缺失
- OI 缺失
- 清算缺失

### 8. 输出优先级

当同一份上下文里同时出现简版字段和详细字段时，优先使用详细字段。

优先级：

1. 明确数值字段：funding、funding_raw、oi_change_pct、long_liq、short_liq
2. 上游 agent 原始分析中的 CoinGlass 资金面说明
3. 市场摘要模板中的占位符
4. 只有前三者都没有，才允许输出“缺失”

<!-- V7_MARKET_SUMMARY_DATA_FIX_FULL_END -->

<!-- V7_OI_FUNDING_JUDGEMENT_FIX_BEGIN -->

## V7 Funding 单位与 OI 字段判断强制修正

### 1. Funding 单位判断

市场摘要中如果 Funding 数值后面已经带有 `%`，必须把它当作“百分比数值”直接判断。

例如：

- Funding = 0.0045%  
  判断值就是 0.0045%，不是 0.45%

- Funding = -0.0011%  
  判断值就是 -0.0011%，不是 -0.11%

- Funding = -0.11%  
  判断值就是 -0.11%

### 2. V7 Funding 通过条件

Funding 只有满足以下任一条件才算 V7 通过：

1. Funding < -0.10%
2. 0.05% <= Funding < 0.10%

其他所有 Funding 都是不通过。

正确判断示例：

- Funding = 0.0045%，V7 不通过
- Funding = -0.0011%，V7 不通过
- Funding = -0.05%，V7 不通过
- Funding = -0.11%，V7 通过
- Funding = 0.053%，V7 通过
- Funding = 0.12%，V7 不通过

禁止错误判断：

- Funding = -0.0011%，V7 通过

这必须改为：

- Funding = -0.0011%，V7 不通过

### 3. raw funding 与百分比 funding 的区别

如果原始字段名是 funding_raw，且数值没有 `%`，需要先判断它的单位。

常见情况：

- raw = 0.000045，可能对应 0.0045%
- raw = -0.000011，可能对应 -0.0011%
- raw = -0.0011，可能对应 -0.11%

市场摘要中最终必须输出带 `%` 的数值，并按最终显示的百分比数值判断 V7 是否通过。

不得把 -0.0011% 错当成 -0.11%。

### 4. OI 4h 字段读取规则

如果上下文里出现以下任意字段，市场摘要不得写 OI 4h 缺失：

- OI
- OI 4h
- OI change_pct
- oi_change_pct
- open_interest
- open_interest_change
- open_interest_change_pct
- CoinGlass 4h OI
- 4h OI
- OI 当前
- OI 变化
- OI change

必须优先提取 4h OI change_pct。

### 5. OI 4h 输出格式

如果 OI 4h change_pct 有数值，必须输出：

- OI 4h：{oi_change_pct}%，V7 {通过/不通过}

V7 OI 通过条件：

- -1.0% < OI change_pct < 1.0%

示例：

- OI 4h：0.0956%，V7 通过
- OI 4h：-0.0146%，V7 通过
- OI 4h：1.25%，V7 不通过
- OI 4h：-1.30%，V7 不通过

### 6. 缺失与不通过必须区分

只有完全没有 OI 字段时，才允许写：

- OI 4h：缺失

如果有 OI 数值，但不满足 V7，必须写：

- OI 4h：{oi_change_pct}%，V7 不通过

不得写：

- OI 4h：缺失

### 7. 市场摘要资金面最终格式

BTC / ETH 每个小节必须尽量输出：

- Funding：{funding_value}%，V7 {通过/不通过}
- OI 4h：{oi_change_pct}%，V7 {通过/不通过}
- 清算：Long {long_liq} USD / Short {short_liq} USD，short/long={ratio}，禁止追多 {触发/未触发}

### 8. 结论联动

如果 Funding 不通过，即使 OI 和清算通过，资金面仍然不通过。

如果 OI 缺失，必须写：

- 资金面不完整，V7 未完整通过

如果 OI 有数值但不通过，必须写：

- 资金面不通过，V7 未完整通过

如果 short_liq > long_liq × 4 且 short_liq > 1,000,000 USD，必须写：

- 触发禁止追多，当前仓位 0%

<!-- V7_OI_FUNDING_JUDGEMENT_FIX_END -->

<!-- V7_OI_TOTAL_CHANGE_FIX_BEGIN -->

## V7 OI 总OI与变动字段强制读取规则

### 1. 禁止输出“币种级缺失”

市场摘要中禁止输出：

- OI 4h：币种级缺失
- OI 4h：币种级缺失；CoinGlass 总OI：xxx，变动 yyy%

如果上下文中已经出现：

- CoinGlass 总OI
- 总OI
- total OI
- open interest
- 变动
- change
- change_pct
- OI change

并且同时存在一个百分比变动数值，则必须把该百分比作为 OI 4h change_pct 输出。

### 2. 正确输出格式

如果原始内容是：

CoinGlass 总OI：103,430,467.283 USD，变动 -0.59%

市场摘要必须输出为：

- OI 4h：-0.59%，V7 通过；CoinGlass 总OI：103,430,467.283 USD

不得输出：

- OI 4h：币种级缺失；CoinGlass 总OI：103,430,467.283 USD，变动 -0.59%

### 3. OI 通过判断

V7 OI 通过条件：

- -1.0% < OI change_pct < 1.0%

判断示例：

- OI 4h：-0.59%，V7 通过
- OI 4h：0.0956%，V7 通过
- OI 4h：-0.0146%，V7 通过
- OI 4h：1.25%，V7 不通过
- OI 4h：-1.30%，V7 不通过

### 4. 只有缺少变动百分比时才允许写不完整

如果只有 CoinGlass 总OI，但没有任何 OI 变动百分比，才允许写：

- OI 4h：change_pct 缺失；CoinGlass 总OI：{total_oi}

不得写：

- OI 4h：币种级缺失

### 5. 市场摘要最终 OI 行格式

BTC / ETH 每个小节的 OI 行必须尽量写成：

- OI 4h：{oi_change_pct}%，V7 {通过/不通过}；CoinGlass 总OI：{total_oi} USD

如果没有 total_oi，但有 oi_change_pct，则写：

- OI 4h：{oi_change_pct}%，V7 {通过/不通过}

如果完全没有 OI 数据，才写：

- OI 4h：缺失

<!-- V7_OI_TOTAL_CHANGE_FIX_END -->

<!-- V7_MARKET_SUMMARY_NO_META_ECHO_BEGIN -->

## V7 市场摘要禁止回显测试指令规则

市场摘要、每日摘要、每4小时报告、BTC/ETH 市场报告中，禁止输出对用户指令的解释或回显。

禁止出现以下类型文字：

- 本次已按要求输出
- 已按要求
- 按要求
- 不判通过
- 不得判断为通过
- 必须输出
- 不允许写缺失
- 我已修正
- 本次修正
- 根据你的要求

这些是执行规则，不是报告内容。

报告只能输出市场信息、V7 判断、观察区、止损止盈、仓位和总建议。

总建议必须使用交易结论格式，例如：

总建议：BTC 0%；ETH 0%。  
原因：BTC Funding 不通过且清算触发禁止追多；ETH Funding 不通过。两者均未完整通过 V7，当前不开仓，看空仅观察。

禁止输出：

总建议：BTC 0%；ETH 0%。本次已按要求输出 OI 4h 为 CoinGlass 变动百分比，并给出 V7 通过/不通过；-0.0011% Funding 不判通过。

<!-- V7_MARKET_SUMMARY_NO_META_ECHO_END -->

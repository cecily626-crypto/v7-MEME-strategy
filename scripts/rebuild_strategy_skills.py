from pathlib import Path
import re
import shutil
from datetime import datetime

ROOT = Path("/home/ubuntu/crypto-strategy-skills")
SKILLS = ROOT / "skills"
DOCS = ROOT / "docs"
SCRIPTS = ROOT / "scripts"

SKILLS.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)
SCRIPTS.mkdir(parents=True, exist_ok=True)

V7_SRC = Path("/home/ubuntu/.openclaw/skills/initial_long_strategy_v2_v7/SKILL.md")
V7_AGENT = Path("/home/ubuntu/.openclaw/agents/market-analyst-v2/workspace/AGENTS.md")
V7_OUT = SKILLS / "V7_LONG_SKILL.md"

MEME_TOOL = Path("/home/ubuntu/.openclaw/tools/meme_bidir_live_observe_watch.py")
MEME_OUT = SKILLS / "MEME_BIDIR_SKILL.md"

ts = datetime.now().strftime("%Y%m%d_%H%M%S")


def backup(path: Path):
    if path.exists():
        bak = path.with_suffix(path.suffix + f".bak_{ts}")
        shutil.copy2(path, bak)
        print(f"backup: {bak}")


def extract_last_block(text: str, begin: str, end: str) -> str:
    pattern = re.escape(begin) + r".*?" + re.escape(end)
    blocks = re.findall(pattern, text, flags=re.S)
    return blocks[-1].strip() if blocks else ""


def extract_function(text: str, func_name: str, next_func_name: str) -> str:
    pattern = rf"def {re.escape(func_name)}\(.*?\):\n.*?\n(?=def {re.escape(next_func_name)}\(.*?\):)"
    m = re.search(pattern, text, flags=re.S)
    return m.group(0).rstrip() if m else ""


def build_v7():
    if not V7_SRC.exists():
        raise SystemExit(f"missing V7 source: {V7_SRC}")

    backup(V7_OUT)

    base = V7_SRC.read_text(encoding="utf-8")
    agent = V7_AGENT.read_text(encoding="utf-8") if V7_AGENT.exists() else ""

    marker = "## 14. V7 Telegram 市场摘要输出规则"
    idx = base.find(marker)
    if idx != -1:
        base = base[:idx].rstrip()

    blocks = []
    for begin, end in [
        ("<!-- V7_MARKET_SUMMARY_DATA_FIX_FULL_BEGIN -->", "<!-- V7_MARKET_SUMMARY_DATA_FIX_FULL_END -->"),
        ("<!-- V7_OI_FUNDING_JUDGEMENT_FIX_BEGIN -->", "<!-- V7_OI_FUNDING_JUDGEMENT_FIX_END -->"),
        ("<!-- V7_OI_TOTAL_CHANGE_FIX_BEGIN -->", "<!-- V7_OI_TOTAL_CHANGE_FIX_END -->"),
        ("<!-- V7_MARKET_SUMMARY_NO_META_ECHO_BEGIN -->", "<!-- V7_MARKET_SUMMARY_NO_META_ECHO_END -->"),
    ]:
        block = extract_last_block(agent, begin, end)
        if block:
            blocks.append(block)
        else:
            print(f"warning: block not found in AGENTS.md: {begin}")

    section14 = """## 14. V7 Telegram 市场摘要输出规则

本节用于固化 V7 Telegram 市场摘要 / 每4小时报告 / BTC ETH 市场报告的输出纪律。

这些规则来自当前 OpenClaw market-analyst-v2 已修复版本，用于避免换服务器、换模型或迁移到 Claude Code 后再次出现以下问题：

- Funding / OI / 清算明明有数据，却输出“缺失”
- Funding 单位误判
- -0.0011% Funding 被误判为 V7 通过
- OI 4h 明明有 CoinGlass 变动百分比，却输出“币种级缺失”
- 市场摘要结尾回显测试指令
"""

    if blocks:
        section14 += "\n\n" + "\n\n".join(blocks)
    else:
        section14 += """

### 14.1 最小兜底规则

- Funding 必须按 V7 规则判断：Funding < -0.10% 或 0.05% <= Funding < 0.10%。
- Funding = -0.0011% 不通过。
- OI 4h 必须按 -1.0% < OI change_pct < 1.0% 判断。
- 如果 CoinGlass 总OI存在且有变动百分比，必须把变动百分比作为 OI 4h 输出。
- 如果 short_liq > long_liq × 4 且 short_liq > 1,000,000 USD，触发禁止追多。
- 市场摘要不得回显“已按要求”“本次修正”等测试指令。
"""

    V7_OUT.write_text(base.rstrip() + "\n\n---\n\n" + section14.strip() + "\n", encoding="utf-8")
    print(f"rebuilt: {V7_OUT}")


def build_meme():
    backup(MEME_OUT)

    tool_text = MEME_TOOL.read_text(encoding="utf-8") if MEME_TOOL.exists() else ""
    calc_entry_plan = extract_function(tool_text, "calc_entry_plan", "format_alert")

    runtime_note = f"""
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

- {"已提取" if calc_entry_plan else "未提取"}
"""

    impl_ref = ""
    if calc_entry_plan:
        impl_ref = "\n## 12. 当前 OpenClaw calc_entry_plan 实现参考\n\n```python\n" + calc_entry_plan + "\n```\n"

    meme = f"""# MEME-BIDIR Strategy Skill

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

{runtime_note}

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

- 优先回踩观察区间：{{pullback_low}} - {{pullback_high}}
  条件：价格先回踩进入该区间；若不跌破 {{pullback_low}}，并在区间内出现止跌/重新走强信号，可考虑区间内低吸观察；跌破 {{pullback_low}} 则不入场。

- 回踩确认价：{{pullback_high}} 上方
  条件：重新站上 {{pullback_high}} 说明回踩确认成功；若已明显拉离 {{pullback_high}}，不追高。

- 备选突破入场：{{breakout_price}} 上方
  条件：4H 有效站上 {{breakout_price}} 后，回踩不跌破 {{breakout_price}} 再考虑；直接拉升不追。

- 止损建议：
  回踩入场止损：{{pullback_stop_price}}
  突破入场止损：{{breakout_stop_price}}

- 失效参考：
  跌破 {{risk_invalid_price}} 后，当前做多观察失效，重新评估。

## 7. 做空观察输出格式

建议执行：

- 状态：做空观察，不是正式开仓提醒，当前仓位 0%。

- 优先反弹观察区间：{{rebound_low}} - {{rebound_high}}
  条件：价格先反弹进入该区间；若不能有效突破 {{rebound_high}}，并在区间内出现承压/重新走弱信号，可考虑区间内反弹做空观察；突破 {{rebound_high}} 则不入场。

- 反弹确认价：{{rebound_low}} 下方
  条件：重新跌回 {{rebound_low}} 下方，说明反弹失败确认；若已明显跌离 {{rebound_low}}，不追空。

- 备选跌破入场：{{breakdown_price}} 下方
  条件：4H 有效跌破 {{breakdown_price}} 后，反抽不重新站回 {{breakdown_price}} 上方再考虑；直接下杀不追。

- 止损建议：
  反弹入场止损：{{rebound_stop_price}}
  跌破入场止损：{{breakdown_stop_price}}

- 失效参考：
  突破 {{risk_invalid_price}} 后，当前做空观察失效，重新评估。

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

{impl_ref}

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
"""

    MEME_OUT.write_text(meme.strip() + "\n", encoding="utf-8")
    print(f"rebuilt: {MEME_OUT}")


def write_readme():
    readme = """# Crypto Strategy Skills

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
"""
    (ROOT / "README.md").write_text(readme, encoding="utf-8")


def write_runtime_map():
    m = """# OpenClaw Runtime Map

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
"""
    (DOCS / "OPENCLAW_RUNTIME_MAP.md").write_text(m, encoding="utf-8")


def write_verify():
    verify = r'''#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Checking skill files..."

test -f "$ROOT/skills/V7_LONG_SKILL.md"
test -f "$ROOT/skills/MEME_BIDIR_SKILL.md"

grep -q "Funding < -0.10%" "$ROOT/skills/V7_LONG_SKILL.md"
grep -q "0.05% <= Funding < 0.10%" "$ROOT/skills/V7_LONG_SKILL.md"
grep -q -- "-1.0% < 4h OI change_pct < 1.0%" "$ROOT/skills/V7_LONG_SKILL.md"
grep -q "short_liq > long_liq × 4" "$ROOT/skills/V7_LONG_SKILL.md"
grep -q "V7_MARKET_SUMMARY" "$ROOT/skills/V7_LONG_SKILL.md"

grep -q "MEME-BIDIR" "$ROOT/skills/MEME_BIDIR_SKILL.md"
grep -q "做多观察" "$ROOT/skills/MEME_BIDIR_SKILL.md"
grep -q "做空观察" "$ROOT/skills/MEME_BIDIR_SKILL.md"
grep -q "当前仓位 0%" "$ROOT/skills/MEME_BIDIR_SKILL.md"
grep -q "最近3根4H区间数据缺失" "$ROOT/skills/MEME_BIDIR_SKILL.md"
grep -q "回踩入场止损" "$ROOT/skills/MEME_BIDIR_SKILL.md"
grep -q "突破入场止损" "$ROOT/skills/MEME_BIDIR_SKILL.md"
grep -q "反弹入场止损" "$ROOT/skills/MEME_BIDIR_SKILL.md"
grep -q "跌破入场止损" "$ROOT/skills/MEME_BIDIR_SKILL.md"
grep -q "优先回踩观察区间" "$ROOT/skills/MEME_BIDIR_SKILL.md"
grep -q "优先反弹观察区间" "$ROOT/skills/MEME_BIDIR_SKILL.md"

echo "OK: all required strategy rules found."
'''
    p = SCRIPTS / "verify_skills.sh"
    p.write_text(verify, encoding="utf-8")
    p.chmod(0o755)


def main():
    build_v7()
    build_meme()
    write_readme()
    write_runtime_map()
    write_verify()
    print("done: portable strategy skills rebuilt")


if __name__ == "__main__":
    main()

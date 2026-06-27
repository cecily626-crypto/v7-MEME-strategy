#!/usr/bin/env bash
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

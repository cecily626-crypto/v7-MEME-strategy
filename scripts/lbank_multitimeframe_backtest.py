#!/usr/bin/env python3
import csv
import json
import math
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "lbank")
RESULTS_ROOT = os.path.join(ROOT, "results", "lbank_multitimeframe")
DEFAULT_CONFIG = os.path.join(ROOT, "config", "strategies", "quality8_multitimeframe_atr.json")
NOTIFY_STATE_DIR = os.path.join(ROOT, "results", "lbank_multitimeframe_notify")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_env():
    env_path = os.path.join(ROOT, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def http_json(url, timeout=20, retries=2):
    last_error = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "crypto-strategy-lab/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
            time.sleep(1 + attempt)
    raise RuntimeError(f"request failed: {url}: {last_error}")


def mean(values):
    return sum(values) / len(values) if values else None


def ema(values, span):
    if len(values) < span:
        return None
    alpha = 2 / (span + 1)
    value = mean(values[:span])
    for item in values[span:]:
        value = item * alpha + value * (1 - alpha)
    return value


def wma(values):
    if not values:
        return None
    weights = list(range(1, len(values) + 1))
    return sum(v * w for v, w in zip(values, weights)) / sum(weights)


def stdev(values):
    if len(values) < 2:
        return None
    m = mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / (len(values) - 1))


def max_drawdown(equity_values):
    peak = equity_values[0]
    worst = 0.0
    for value in equity_values:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1)
    return worst


def leverage_for(symbol, cfg):
    return float(cfg.get("leverage_by_symbol", {}).get(symbol, cfg.get("leverage_default", 1)))


def base_cap_for(symbol, cfg):
    return float(cfg.get("max_base_weight_by_symbol", {}).get(symbol, cfg["max_base_weight_default"]))


def fee_rate(cfg):
    fee_key = "maker_fee_bps" if cfg.get("paper_fee_mode") == "maker" else "taker_fee_bps"
    return (cfg.get(fee_key, 0) + cfg.get("slippage_bps", 0)) / 10000


def holding_hours(trade):
    return round((trade["exit_ts"] - trade["entry_ts"]) / 3600, 2)


def parse_kline(item):
    ts, open_, high, low, close, volume = item[:6]
    return {
        "ts": int(ts),
        "dt": datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat(),
        "date": datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d"),
        "open": float(open_),
        "high": float(high),
        "low": float(low),
        "close": float(close),
        "volume": float(volume),
    }


def cache_path(symbol, interval):
    return os.path.join(DATA_DIR, f"{symbol}_{interval}.csv")


def read_cache(symbol, interval):
    path = cache_path(symbol, interval)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        rows = []
        for r in csv.DictReader(f):
            if "ts" in r and r.get("ts"):
                ts = int(r["ts"])
                dt = r.get("dt") or datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
                date = r.get("date") or datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            else:
                date = r["date"]
                ts = int(datetime.fromisoformat(date).replace(tzinfo=timezone.utc).timestamp())
                dt = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            rows.append({
                "ts": ts,
                "dt": dt,
                "date": date,
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["volume"]),
            })
        return rows


def write_cache(symbol, interval, rows):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(cache_path(symbol, interval), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ts", "dt", "date", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(rows)


def fetch_lbank_kline(symbol, interval, lookback_days, cfg):
    cached = read_cache(symbol, interval)
    now = int(time.time())
    start = now - lookback_days * 86400
    interval_seconds = {"day1": 86400, "hour4": 14400, "hour1": 3600, "minute15": 900}[interval]
    expected_latest = now - interval_seconds * 3
    if cfg.get("use_cached_data_only") and cached:
        return [r for r in cached if r["ts"] >= start]
    if cached and cached[0]["ts"] <= start + interval_seconds and cached[-1]["ts"] >= expected_latest:
        return [r for r in cached if r["ts"] >= start]

    rows = {}
    cursor = start
    max_size = 2000
    while cursor < now:
        params = urllib.parse.urlencode({
            "symbol": symbol,
            "size": max_size,
            "type": interval,
            "time": cursor,
        })
        url = f"{cfg['lbank_spot_base_url']}/v2/kline.do?{params}"
        try:
            payload = http_json(url)
        except Exception:
            if cached:
                return [r for r in cached if r["ts"] >= start]
            raise
        batch = [parse_kline(item) for item in payload.get("data", [])]
        if not batch:
            break
        for row in batch:
            if row["ts"] >= start:
                rows[row["ts"]] = row
        next_cursor = max(row["ts"] for row in batch) + interval_seconds
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        if len(batch) < max_size:
            break
        time.sleep(0.15)

    merged = {r["ts"]: r for r in cached if r["ts"] >= start}
    merged.update(rows)
    out = [merged[k] for k in sorted(merged)]
    if out:
        write_cache(symbol, interval, out)
    return out


def asof_index(rows, ts):
    lo, hi = 0, len(rows) - 1
    ans = -1
    while lo <= hi:
        mid = (lo + hi) // 2
        if rows[mid]["ts"] <= ts:
            ans = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return ans


def true_ranges(rows):
    out = []
    for i in range(1, len(rows)):
        high = rows[i]["high"]
        low = rows[i]["low"]
        prev_close = rows[i - 1]["close"]
        out.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return out


def atr_wma(rows, bars):
    if len(rows) < bars + 1:
        return None
    return wma(true_ranges(rows)[-bars:])


def adx(rows, bars):
    if len(rows) < bars + 2:
        return None
    plus_dm = []
    minus_dm = []
    trs = []
    for i in range(1, len(rows)):
        up_move = rows[i]["high"] - rows[i - 1]["high"]
        down_move = rows[i - 1]["low"] - rows[i]["low"]
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)
        trs.append(max(
            rows[i]["high"] - rows[i]["low"],
            abs(rows[i]["high"] - rows[i - 1]["close"]),
            abs(rows[i]["low"] - rows[i - 1]["close"]),
        ))
    if len(trs) < bars:
        return None
    tr = sum(trs[-bars:])
    if tr <= 0:
        return None
    plus_di = 100 * sum(plus_dm[-bars:]) / tr
    minus_di = 100 * sum(minus_dm[-bars:]) / tr
    denom = plus_di + minus_di
    if denom <= 0:
        return None
    return 100 * abs(plus_di - minus_di) / denom


def ema_slope(closes, span, lookback):
    if len(closes) < span + lookback:
        return None
    now = ema(closes, span)
    prev = ema(closes[:-lookback], span)
    if not now or not prev:
        return None
    return now / prev - 1


def side(cfg):
    return cfg.get("side", "long")


def direction_sign(cfg):
    return -1 if side(cfg) == "short" else 1


def stop_triggered(pos, bar, cfg):
    use_close = cfg.get("stop_trigger", "intrabar") == "close"
    if pos["side"] == "short":
        return bar["close"] >= pos["stop"] if use_close else bar["high"] >= pos["stop"]
    return bar["close"] <= pos["stop"] if use_close else bar["low"] <= pos["stop"]


def trailing_is_active(pos, bar, cfg):
    delay_bars = cfg.get("trailing_delay_bars", 0)
    interval_seconds = 3600
    held_bars = (bar["ts"] - pos["entry_ts"]) / interval_seconds
    if held_bars < delay_bars:
        return False
    activation_r = cfg.get("trailing_activation_r", 0)
    if activation_r <= 0:
        return True
    if pos["side"] == "short":
        favorable = pos["entry"] - pos["lowest"]
    else:
        favorable = pos["highest"] - pos["entry"]
    return favorable >= activation_r * pos["initial_r"]


def daily_direction(rows, cfg):
    if len(rows) < cfg["daily_slow_sma_days"] + 1:
        return False
    closes = [r["close"] for r in rows]
    fast = mean(closes[-cfg["daily_fast_sma_days"]:])
    slow = mean(closes[-cfg["daily_slow_sma_days"]:])
    momentum = closes[-1] / closes[-cfg["daily_momentum_days"]] - 1
    if side(cfg) == "short":
        return closes[-1] < slow and fast < slow and momentum < 0
    return closes[-1] > slow and fast > slow and momentum > 0


def trend_strength_ok(rows, cfg):
    adx_bars = cfg.get("hour4_adx_bars")
    min_adx = cfg.get("hour4_min_adx")
    if adx_bars and min_adx and (adx(rows, adx_bars) or 0) < min_adx:
        return False
    slope_bars = cfg.get("hour4_ema_slope_bars")
    min_slope = cfg.get("hour4_min_ema_slope")
    if slope_bars and min_slope:
        closes = [r["close"] for r in rows]
        slope = ema_slope(closes, cfg["hour4_fast_ema_bars"], slope_bars)
        if slope is None:
            return False
        if side(cfg) == "short":
            return slope <= -min_slope
        return slope >= min_slope
    return True


def hour4_confirm(rows, cfg):
    need = max(cfg["hour4_slow_ema_bars"], cfg["hour4_volume_average_bars"], cfg["hour4_momentum_bars"]) + 1
    if len(rows) < need:
        return False
    closes = [r["close"] for r in rows]
    volumes = [r["volume"] for r in rows]
    fast = ema(closes, cfg["hour4_fast_ema_bars"])
    slow = ema(closes, cfg["hour4_slow_ema_bars"])
    momentum = closes[-1] / closes[-cfg["hour4_momentum_bars"]] - 1
    volume_ok = volumes[-1] >= mean(volumes[-cfg["hour4_volume_average_bars"]:]) * cfg["hour4_volume_multiple"]
    if side(cfg) == "short":
        return closes[-1] < fast and fast < slow and momentum < 0 and volume_ok and trend_strength_ok(rows, cfg)
    return closes[-1] > fast and fast > slow and momentum > 0 and volume_ok and trend_strength_ok(rows, cfg)


def hour4_trend_ok(rows, cfg):
    need = max(cfg["hour4_slow_ema_bars"], cfg["hour4_momentum_bars"]) + 1
    if len(rows) < need:
        return False
    closes = [r["close"] for r in rows]
    fast = ema(closes, cfg["hour4_fast_ema_bars"])
    slow = ema(closes, cfg["hour4_slow_ema_bars"])
    momentum = closes[-1] / closes[-cfg["hour4_momentum_bars"]] - 1
    if side(cfg) == "short":
        return closes[-1] < fast and fast < slow and momentum < 0
    return closes[-1] > fast and fast > slow and momentum > 0


def entry_trigger(rows, cfg):
    need = max(cfg["entry_ema_bars"], cfg["entry_breakout_bars"], cfg["atr_bars"] + 1) + 2
    if len(rows) < need:
        return False
    closes = [r["close"] for r in rows]
    current_ema = ema(closes, cfg["entry_ema_bars"])
    prev_ema = ema(closes[:-1], cfg["entry_ema_bars"])
    if side(cfg) == "short":
        breakdown = min(r["low"] for r in rows[-cfg["entry_breakout_bars"] - 1:-1])
        regained_ema = closes[-2] >= prev_ema and closes[-1] < current_ema
        constructive_breakout = closes[-1] < breakdown and closes[-1] < current_ema
        return regained_ema or constructive_breakout
    breakout = max(r["high"] for r in rows[-cfg["entry_breakout_bars"] - 1:-1])
    regained_ema = closes[-2] <= prev_ema and closes[-1] > current_ema
    constructive_breakout = closes[-1] > breakout and closes[-1] > current_ema
    return regained_ema or constructive_breakout


def load_market(cfg):
    market = {}
    for symbol in cfg["symbols"]:
        market[symbol] = {
            "day1": fetch_lbank_kline(symbol, "day1", cfg["lookback_days"], cfg),
            "hour4": fetch_lbank_kline(symbol, "hour4", cfg["lookback_days"], cfg),
            "hour1": fetch_lbank_kline(symbol, "hour1", cfg["lookback_days"], cfg),
        }
    return market


def size_base_weight(symbol, entry, stop, cfg, risk_per_trade=None):
    stop_pct = abs(entry - stop) / entry
    stop_pct = max(stop_pct, 1e-6)
    leverage = leverage_for(symbol, cfg)
    risk = cfg["risk_per_trade"] if risk_per_trade is None else risk_per_trade
    risk_cap = risk / (stop_pct * leverage)
    return min(base_cap_for(symbol, cfg), risk_cap)


def trend_risk_per_trade(symbol, rows, market, ts, cfg):
    base = cfg["risk_per_trade"]
    strong = cfg.get("strong_trend_risk_per_trade")
    if not strong:
        return base
    strong_symbols = cfg.get("strong_trend_symbols")
    if strong_symbols and symbol not in set(strong_symbols):
        return base
    if cfg.get("strong_trend_requires_btc", True):
        btc = market.get("btc_usdt")
        if not btc:
            return base
        btc_h4_idx = asof_index(btc["hour4"], ts - 14400)
        if btc_h4_idx < 0:
            return base
        btc_h4 = btc["hour4"][: btc_h4_idx + 1]
        if not trend_strength_ok(btc_h4, cfg):
            return base
    min_adx = cfg.get("strong_trend_min_adx")
    min_slope = cfg.get("strong_trend_min_ema_slope")
    if min_adx and (adx(rows, cfg.get("hour4_adx_bars", 14)) or 0) < min_adx:
        return base
    if min_slope:
        closes = [r["close"] for r in rows]
        slope = ema_slope(closes, cfg["hour4_fast_ema_bars"], cfg.get("hour4_ema_slope_bars", 6))
        if slope is None:
            return base
        if side(cfg) == "short" and slope > -min_slope:
            return base
        if side(cfg) != "short" and slope < min_slope:
            return base
    return strong


def market_filter_ok(market, ts, cfg):
    if not cfg.get("btc_market_filter"):
        return True
    btc = market.get("btc_usdt")
    if not btc:
        return False
    d_idx = asof_index(btc["day1"], ts - 86400)
    h4_idx = asof_index(btc["hour4"], ts - 14400)
    if min(d_idx, h4_idx) < 0:
        return False
    btc_day = btc["day1"][: d_idx + 1]
    btc_h4 = btc["hour4"][: h4_idx + 1]
    return daily_direction(btc_day, cfg) and hour4_trend_ok(btc_h4, cfg) and trend_strength_ok(btc_h4, cfg)


def run_backtest(cfg):
    out_dir = os.path.join(RESULTS_ROOT, cfg["strategy_id"])
    os.makedirs(out_dir, exist_ok=True)
    market = load_market(cfg)
    end_ts = min(v["hour1"][-1]["ts"] for v in market.values() if v["hour1"])
    start_ts = end_ts - cfg["simulation_days"] * 86400
    equity = cfg["initial_equity_usdt"]
    peak = equity
    fee = fee_rate(cfg)
    positions = {}
    equity_rows = []
    trades = []
    fees_paid = 0.0
    funding_paid = 0.0
    liquidations = 0
    cooldown_until = {}

    timeline = sorted({r["ts"] for v in market.values() for r in v["hour1"] if start_ts <= r["ts"] <= end_ts})

    for ts in timeline:
        mark_prices = {}
        target_entries = []
        market_ok = market_filter_ok(market, ts, cfg)

        for symbol, data in market.items():
            h1_idx = asof_index(data["hour1"], ts)
            d_idx = asof_index(data["day1"], ts - 86400)
            h4_idx = asof_index(data["hour4"], ts - 14400)
            if min(h1_idx, d_idx, h4_idx) < 0:
                continue
            h1_rows = data["hour1"][: h1_idx + 1]
            d_rows = data["day1"][: d_idx + 1]
            h4_rows = data["hour4"][: h4_idx + 1]
            bar = h1_rows[-1]
            mark_prices[symbol] = bar["close"]

            pos = positions.get(symbol)
            if pos:
                atr = atr_wma(h1_rows, cfg["atr_bars"])
                if atr:
                    if pos["side"] == "short":
                        pos["lowest"] = min(pos["lowest"], bar["low"])
                        if trailing_is_active(pos, bar, cfg):
                            multiple = cfg.get("trailing_atr_multiple", cfg["atr_multiple"])
                            pos["stop"] = min(pos["stop"], pos["lowest"] + multiple * atr)
                    else:
                        pos["highest"] = max(pos["highest"], bar["high"])
                        if trailing_is_active(pos, bar, cfg):
                            multiple = cfg.get("trailing_atr_multiple", cfg["atr_multiple"])
                            pos["stop"] = max(pos["stop"], pos["highest"] - multiple * atr)
                exit_reason = None
                exit_price = None
                if pos["side"] == "short":
                    liquidation_price = pos["entry"] * (1 + 1 / leverage_for(symbol, cfg))
                    stop_hit = stop_triggered(pos, bar, cfg)
                    liquidated = bar["high"] >= liquidation_price
                else:
                    liquidation_price = pos["entry"] * (1 - 1 / leverage_for(symbol, cfg))
                    stop_hit = stop_triggered(pos, bar, cfg)
                    liquidated = bar["low"] <= liquidation_price
                if liquidated:
                    exit_reason = "liquidation"
                    exit_price = liquidation_price
                    liquidations += 1
                elif stop_hit:
                    exit_reason = "atr_stop"
                    exit_price = pos["stop"]
                elif not hour4_trend_ok(h4_rows, cfg):
                    exit_reason = "hour4_trend_end"
                    exit_price = bar["close"]
                elif not daily_direction(d_rows, cfg):
                    exit_reason = "daily_trend_end"
                    exit_price = bar["close"]

                if exit_reason:
                    pnl = equity * pos["nominal_weight"] * pos["direction"] * (exit_price / pos["entry"] - 1)
                    cost = equity * pos["nominal_weight"] * fee
                    equity += pnl - cost
                    fees_paid += cost
                    trade = dict(pos)
                    trade.update({
                        "exit_ts": ts,
                        "exit_dt": bar["dt"],
                        "exit_price": exit_price,
                        "exit_reason": exit_reason,
                        "pnl_usdt": pnl - cost,
                        "return_pct": pos["direction"] * (exit_price / pos["entry"] - 1) * 100,
                    })
                    trade["holding_hours"] = holding_hours(trade)
                    trades.append(trade)
                    del positions[symbol]
                    cooldown_until[symbol] = ts + int(cfg.get("cooldown_hours_after_exit", 0) * 3600)
                    continue

            in_cooldown = ts < cooldown_until.get(symbol, 0)
            if market_ok and not in_cooldown and symbol not in positions and daily_direction(d_rows, cfg) and hour4_confirm(h4_rows, cfg) and entry_trigger(h1_rows, cfg):
                atr = atr_wma(h1_rows, cfg["atr_bars"])
                if not atr:
                    continue
                entry = bar["close"]
                stop_distance = cfg["atr_multiple"] * atr
                min_stop_pct = cfg.get("min_initial_stop_pct", 0)
                if min_stop_pct:
                    stop_distance = max(stop_distance, entry * min_stop_pct)
                if side(cfg) == "short":
                    stop = entry + stop_distance
                    invalid_stop = stop <= entry
                    score = (h1_rows[-cfg["entry_breakout_bars"]]["close"] / entry - 1) / max(atr / entry, 1e-6)
                else:
                    stop = entry - stop_distance
                    invalid_stop = stop <= 0 or stop >= entry
                    score = (entry / h1_rows[-cfg["entry_breakout_bars"]]["close"] - 1) / max(atr / entry, 1e-6)
                if invalid_stop:
                    continue
                effective_risk = trend_risk_per_trade(symbol, h4_rows, market, ts, cfg)
                base_weight = size_base_weight(symbol, entry, stop, cfg, effective_risk)
                if base_weight > 0:
                    target_entries.append((score, symbol, entry, stop, base_weight, bar, effective_risk))

        current_gross = sum(p["nominal_weight"] for p in positions.values())
        free_gross = max(0.0, cfg["max_gross_exposure"] - current_gross)
        free_slots = max(0, cfg["max_positions"] - len(positions))
        for _, symbol, entry, stop, base_weight, bar, effective_risk in sorted(target_entries, reverse=True)[:free_slots]:
            leverage = leverage_for(symbol, cfg)
            nominal_weight = min(base_weight * leverage, free_gross)
            if nominal_weight <= 1e-9:
                continue
            base_weight = nominal_weight / leverage
            cost = equity * nominal_weight * fee
            equity -= cost
            fees_paid += cost
            positions[symbol] = {
                "symbol": symbol,
                "side": side(cfg),
                "direction": direction_sign(cfg),
                "entry_ts": ts,
                "entry_dt": bar["dt"],
                "entry": entry,
                "base_weight": base_weight,
                "nominal_weight": nominal_weight,
                "leverage": leverage,
                "initial_stop": stop,
                "initial_r": abs(entry - stop),
                "risk_per_trade": effective_risk,
                "stop": stop,
                "highest": bar["high"],
                "lowest": bar["low"],
            }
            free_gross -= nominal_weight

        gross = sum(p["nominal_weight"] for p in positions.values())
        funding = equity * gross * cfg.get("funding_daily_rate", 0) / 24
        equity -= funding
        funding_paid += funding

        mtm = equity
        for symbol, pos in positions.items():
            price = mark_prices.get(symbol, pos["entry"])
            mtm += equity * pos["nominal_weight"] * pos["direction"] * (price / pos["entry"] - 1)
        peak = max(peak, mtm)
        equity_rows.append({
            "ts": ts,
            "dt": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
            "equity": round(mtm, 4),
            "cash_equity": round(equity, 4),
            "gross_exposure": round(gross, 6),
            "open_positions": len(positions),
            "drawdown": mtm / peak - 1 if peak else 0,
        })

    for symbol, pos in list(positions.items()):
        data = market[symbol]["hour1"]
        idx = asof_index(data, end_ts)
        price = data[idx]["close"]
        cost = equity * pos["nominal_weight"] * fee
        pnl = equity * pos["nominal_weight"] * pos["direction"] * (price / pos["entry"] - 1)
        equity += pnl - cost
        fees_paid += cost
        trade = dict(pos)
        trade.update({
            "exit_ts": end_ts,
            "exit_dt": data[idx]["dt"],
            "exit_price": price,
            "exit_reason": "open_at_end",
            "pnl_usdt": pnl - cost,
            "return_pct": pos["direction"] * (price / pos["entry"] - 1) * 100,
        })
        trade["holding_hours"] = holding_hours(trade)
        trades.append(trade)
        del positions[symbol]
        cooldown_until[symbol] = end_ts + int(cfg.get("cooldown_hours_after_exit", 0) * 3600)

    final_equity = equity_rows[-1]["equity"] if equity_rows else equity
    returns = [equity_rows[i]["equity"] / equity_rows[i - 1]["equity"] - 1 for i in range(1, len(equity_rows)) if equity_rows[i - 1]["equity"]]
    wins = sum(1 for t in trades if t["pnl_usdt"] > 0)
    summary = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "strategy_id": cfg["strategy_id"],
        "display_name": cfg["display_name"],
        "start_dt": equity_rows[0]["dt"] if equity_rows else None,
        "end_dt": equity_rows[-1]["dt"] if equity_rows else None,
        "initial_equity_usdt": cfg["initial_equity_usdt"],
        "ending_equity_usdt": round(final_equity, 2),
        "pnl_usdt": round(final_equity - cfg["initial_equity_usdt"], 2),
        "return_pct": round((final_equity / cfg["initial_equity_usdt"] - 1) * 100, 2),
        "annualized_return_pct": round(((final_equity / cfg["initial_equity_usdt"]) ** (365 / cfg["simulation_days"]) - 1) * 100, 2),
        "max_drawdown_pct": round(max_drawdown([r["equity"] for r in equity_rows]) * 100, 2) if equity_rows else 0,
        "annualized_volatility_pct": round((stdev(returns) or 0) * math.sqrt(24 * 365) * 100, 2),
        "trade_count": len(trades),
        "win_rate_pct": round(wins / len(trades) * 100, 2) if trades else None,
        "fees_paid_usdt": round(fees_paid, 2),
        "funding_paid_usdt": round(funding_paid, 2),
        "liquidation_count": liquidations,
        "avg_holding_hours": round(mean([t["holding_hours"] for t in trades]) or 0, 2) if trades else None,
    }

    with open(os.path.join(out_dir, "summary_90d.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    with open(os.path.join(out_dir, "equity_90d.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ts", "dt", "equity", "cash_equity", "gross_exposure", "open_positions", "drawdown"])
        writer.writeheader()
        writer.writerows(equity_rows)
    fields = ["symbol", "side", "entry_dt", "entry", "base_weight", "nominal_weight", "leverage", "risk_per_trade", "initial_stop", "exit_dt", "exit_price", "exit_reason", "pnl_usdt", "return_pct", "holding_hours"]
    with open(os.path.join(out_dir, "trades_90d.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for trade in trades:
            writer.writerow({k: trade.get(k) for k in fields})
    return summary


def send_telegram(text):
    load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(text)
        print("\nTelegram not sent: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing.")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    last_error = None
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req, timeout=30) as r:
                payload = json.loads(r.read().decode("utf-8"))
            ok = bool(payload.get("ok"))
            if ok:
                print(f"Telegram sent successfully on attempt {attempt}.")
                return True
            last_error = payload
            print(f"Telegram send failed on attempt {attempt}: {payload}")
        except Exception as exc:
            last_error = exc
            print(f"Telegram send error on attempt {attempt}: {exc}")
        time.sleep(2 * attempt)
    print(f"Telegram urllib delivery failed after retries: {last_error}")
    try:
        result = subprocess.run(
            [
                "/usr/bin/curl",
                "-sS",
                "--fail",
                "--retry", "5",
                "--retry-delay", "2",
                "--connect-timeout", "20",
                "--max-time", "60",
                "-X", "POST",
                "-d", f"chat_id={chat_id}",
                "--data-urlencode", f"text={text}",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=90,
        )
        if result.returncode == 0:
            payload = json.loads(result.stdout)
            ok = bool(payload.get("ok"))
            print("Telegram sent successfully via curl fallback." if ok else f"Telegram curl send failed: {payload}")
            return ok
        print(f"Telegram curl error: {result.stderr.strip() or result.stdout.strip()}")
    except Exception as exc:
        print(f"Telegram curl fallback exception: {exc}")
    return False


def trade_key(trade):
    return f"{trade['symbol']}|{trade.get('side')}|{trade['entry_dt']}|{trade.get('exit_dt')}"


def entry_key(trade):
    return f"{trade['symbol']}|{trade.get('side')}|{trade['entry_dt']}"


def format_entry_line(trade):
    direction = "做空" if trade.get("side") == "short" else "做多"
    return (
        f"- {trade['symbol']} {direction}: 入场 {float(trade['entry']):.8g} / "
        f"初始止损 {float(trade['initial_stop']):.8g} / "
        f"基础仓位 {float(trade['base_weight']) * 100:.2f}% / "
        f"名义仓位 {float(trade['nominal_weight']) * 100:.2f}% / "
        f"账户风险 {float(trade.get('risk_per_trade') or 0) * 100:.2f}%"
    )


def format_trade_line(trade):
    direction = "做空" if trade.get("side") == "short" else "做多"
    return (
        f"- {trade['symbol']} {direction}: 入场 {float(trade['entry']):.8g} / "
        f"离场 {float(trade['exit_price']):.8g} / "
        f"盈亏 {float(trade['pnl_usdt']):+.2f} USDT ({float(trade['return_pct']):+.2f}%) / "
        f"持仓 {float(trade.get('holding_hours') or 0):.1f}h / 原因 {trade.get('exit_reason')}"
    )


def parse_iso_dt(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def trades_in_period(trades, start_dt, end_dt):
    period = []
    for trade in trades:
        entry_dt = parse_iso_dt(trade["entry_dt"]) if trade.get("entry_dt") else None
        exit_dt = parse_iso_dt(trade["exit_dt"]) if trade.get("exit_dt") else None
        if (entry_dt and start_dt <= entry_dt < end_dt) or (exit_dt and start_dt <= exit_dt < end_dt):
            period.append(trade)
    return period


def period_summary_lines(trades, start_dt, end_dt):
    period_trades = trades_in_period(trades, start_dt, end_dt)
    closed = [t for t in period_trades if t.get("exit_dt") and t.get("exit_reason") != "open_at_end"]
    entries = [t for t in period_trades if t.get("entry_dt") and start_dt <= parse_iso_dt(t["entry_dt"]) < end_dt]
    exits = [t for t in closed if t.get("exit_dt") and start_dt <= parse_iso_dt(t["exit_dt"]) < end_dt]
    pnl = sum(float(t.get("pnl_usdt") or 0) for t in exits)
    wins = sum(1 for t in exits if float(t.get("pnl_usdt") or 0) > 0)
    avg_holding = mean([float(t.get("holding_hours") or 0) for t in exits]) if exits else None
    symbols = sorted({t.get("symbol", "") for t in period_trades if t.get("symbol")})
    win_rate = f"{wins / len(exits) * 100:.2f}%" if exits else "暂无"
    return [
        f"本周窗口: {start_dt.date()} 至 {(end_dt - timedelta(seconds=1)).date()}",
        f"本周新增开仓: {len(entries)} / 新增平仓: {len(exits)} / 胜率: {win_rate}",
        f"本周已平仓盈亏: {pnl:+.2f} USDT",
        f"本周交易币对: {', '.join(symbols) if symbols else '无'}",
        f"本周平均持仓: {avg_holding:.1f}h" if avg_holding is not None else "本周平均持仓: 暂无",
    ]


def notify_latest(cfg):
    summary = run_backtest(cfg)
    out_dir = os.path.join(RESULTS_ROOT, cfg["strategy_id"])
    trades_path = os.path.join(out_dir, "trades_90d.csv")
    trades = []
    if os.path.exists(trades_path):
        with open(trades_path, "r", encoding="utf-8") as f:
            trades = list(csv.DictReader(f))

    os.makedirs(NOTIFY_STATE_DIR, exist_ok=True)
    state_path = os.path.join(NOTIFY_STATE_DIR, f"{cfg['strategy_id']}.json")
    state = load_json(state_path) if os.path.exists(state_path) else {"notified_entries": [], "notified_exits": []}
    seen_entries = set(state.get("notified_entries", []))
    seen_exits = set(state.get("notified_exits", []))
    new_entries = [t for t in trades if entry_key(t) not in seen_entries]
    new_exits = [t for t in trades if trade_key(t) not in seen_exits and t.get("exit_reason") != "open_at_end"]
    has_new_activity = bool(new_entries or new_exits)
    end_dt = parse_iso_dt(summary["end_dt"]) if summary.get("end_dt") else datetime.now(timezone.utc)
    week_start = end_dt - timedelta(days=7)

    lines = [
        f"LBank 多周期小时观察: {cfg['display_name']}",
        "说明: 本消息只在新增开仓/平仓时推送；下方90日数据是滚动模拟账户表现，不代表本周新增盈亏。",
        *period_summary_lines(trades, week_start, end_dt),
        "",
        "90日滚动模拟:",
        f"- 区间: {summary['start_dt']} 至 {summary['end_dt']}",
        f"- 权益: {summary['ending_equity_usdt']:.2f} USDT / 累计盈亏 {summary['pnl_usdt']:+.2f} USDT ({summary['return_pct']:+.2f}%)",
        f"- 最大回撤: {summary['max_drawdown_pct']:.2f}% / 交易数: {summary['trade_count']} / 胜率: {summary['win_rate_pct']}%",
        f"- 手续费: {summary['fees_paid_usdt']:.2f} USDT / 资金费率: {summary['funding_paid_usdt']:.2f} USDT",
        "新增开仓:",
    ]
    if new_entries:
        for trade in new_entries[-20:]:
            lines.append(format_entry_line(trade))
    else:
        lines.append("- 无")
    lines += [
        "新增平仓:",
    ]
    if new_exits:
        for trade in new_exits[-20:]:
            lines.append(format_trade_line(trade))
    else:
        lines.append("- 无")

    state["notified_entries"] = sorted(seen_entries | {entry_key(t) for t in new_entries})
    state["notified_exits"] = sorted(seen_exits | {trade_key(t) for t in new_exits})
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    text = "\n".join(lines)
    if has_new_activity:
        send_telegram(text)
    else:
        print("No new multitimeframe entries/exits; Telegram not sent.")
        print(text)
    summary["notification_sent"] = has_new_activity
    summary["new_entries"] = len(new_entries)
    summary["new_exits"] = len(new_exits)
    return summary


def seed_notify_state(cfg):
    summary = run_backtest(cfg)
    out_dir = os.path.join(RESULTS_ROOT, cfg["strategy_id"])
    trades_path = os.path.join(out_dir, "trades_90d.csv")
    trades = []
    if os.path.exists(trades_path):
        with open(trades_path, "r", encoding="utf-8") as f:
            trades = list(csv.DictReader(f))
    os.makedirs(NOTIFY_STATE_DIR, exist_ok=True)
    state_path = os.path.join(NOTIFY_STATE_DIR, f"{cfg['strategy_id']}.json")
    state = {
        "seeded_at_utc": datetime.now(timezone.utc).isoformat(),
        "notified_entries": sorted({entry_key(t) for t in trades}),
        "notified_exits": sorted({trade_key(t) for t in trades if t.get("exit_reason") != "open_at_end"}),
    }
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    print(f"Seeded notify state for {cfg['strategy_id']}: {len(state['notified_entries'])} entries, {len(state['notified_exits'])} exits.")
    return summary


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "backtest"
    if command in {"backtest", "notify", "seed-notify"}:
        config_arg = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_CONFIG
    else:
        command = "backtest"
        config_arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONFIG
    cfg = load_json(config_arg)
    if command == "notify":
        print(json.dumps(notify_latest(cfg), indent=2))
    elif command == "seed-notify":
        print(json.dumps(seed_notify_state(cfg), indent=2))
    else:
        print(json.dumps(run_backtest(cfg), indent=2))


if __name__ == "__main__":
    main()

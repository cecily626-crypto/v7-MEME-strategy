#!/usr/bin/env python3
import csv
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG_PATH = os.path.join(ROOT, "config", "lbank_paper.json")
STRATEGY_CONFIG_DIR = os.path.join(ROOT, "config", "strategies")
RESULTS_ROOT = os.path.join(ROOT, "results", "lbank_paper")
DATA_DIR = os.path.join(ROOT, "data", "lbank")


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


def stdev(values):
    if len(values) < 2:
        return None
    m = mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / (len(values) - 1))


def max_drawdown(equity):
    peak = equity[0]
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1)
    return worst


def strategy_id(cfg):
    return cfg.get("strategy_id") or cfg.get("account_name") or "default"


def result_dir(cfg):
    path = os.path.join(RESULTS_ROOT, strategy_id(cfg))
    os.makedirs(path, exist_ok=True)
    return path


def leverage_for(symbol, cfg):
    return float(cfg.get("leverage_by_symbol", {}).get(symbol, cfg.get("leverage_default", 1)))


def fee_rate(cfg):
    fee_key = "maker_fee_bps" if cfg.get("paper_fee_mode") == "maker" else "taker_fee_bps"
    return (cfg.get(fee_key, cfg.get("fee_bps", 0)) + cfg.get("slippage_bps", 0)) / 10000


def fetch_lbank_daily(symbol, cfg):
    os.makedirs(DATA_DIR, exist_ok=True)
    cache_path = os.path.join(DATA_DIR, f"{symbol}_day1.csv")

    def read_cache():
        if not os.path.exists(cache_path):
            return []
        with open(cache_path, "r", encoding="utf-8") as f:
            return [
                {
                    "date": r["date"],
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r["volume"]),
                }
                for r in csv.DictReader(f)
            ]

    start_ts = int(time.time()) - cfg["lookback_days"] * 86400
    params = urllib.parse.urlencode({
        "symbol": symbol,
        "size": min(2000, cfg["lookback_days"]),
        "type": cfg["timeframe"],
        "time": start_ts,
    })
    url = f"{cfg['lbank_spot_base_url']}/v2/kline.do?{params}"
    try:
        payload = http_json(url)
    except Exception:
        cached = read_cache()
        if cached:
            return cached
        raise

    rows = []
    for item in payload.get("data", []):
        ts, open_, high, low, close, volume = item[:6]
        rows.append({
            "date": datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d"),
            "open": float(open_),
            "high": float(high),
            "low": float(low),
            "close": float(close),
            "volume": float(volume),
        })
    rows = sorted({r["date"]: r for r in rows}.values(), key=lambda r: r["date"])
    with open(cache_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def fetch_funding_rates(cfg):
    params = urllib.parse.urlencode({"productGroup": cfg["lbank_perp_product_group"]})
    url = f"{cfg['lbank_perp_base_url']}/cfd/openApi/v1/pub/marketData?{params}"
    try:
        payload = http_json(url, timeout=12, retries=1)
        rates = {}
        for item in payload.get("data", payload if isinstance(payload, list) else []):
            symbol = str(item.get("symbol", "")).lower()
            rate = item.get("prePositionFeeRate") or item.get("fundingRate") or item.get("positionFeeRate")
            if symbol and rate not in (None, ""):
                rates[symbol] = float(rate)
        return rates, None
    except Exception as exc:
        return {}, str(exc)


def load_market(cfg):
    data = {symbol: fetch_lbank_daily(symbol, cfg) for symbol in cfg["symbols"]}
    data = {s: rows for s, rows in data.items() if len(rows) > cfg["slow_sma_days"] + 5}
    by_symbol = {s: {r["date"]: r for r in rows} for s, rows in data.items()}
    dates = sorted(set.intersection(*(set(v) for v in by_symbol.values())))
    return list(data.keys()), dates, by_symbol


def calculate_base_weights(index, dates, by_symbol, symbols, cfg, equity, peak):
    if index < cfg["slow_sma_days"] + 1:
        return {s: 0.0 for s in symbols}
    candidates = []
    for symbol in symbols:
        rows = [by_symbol[symbol][d] for d in dates[: index + 1]]
        prices = [r["close"] for r in rows]
        volumes = [r["volume"] for r in rows]
        fast = mean(prices[-cfg["fast_sma_days"]:])
        slow = mean(prices[-cfg["slow_sma_days"]:])
        momentum = prices[-1] / prices[-cfg["momentum_days"]] - 1
        returns = [prices[i] / prices[i - 1] - 1 for i in range(len(prices) - cfg["volatility_days"], len(prices))]
        vol = stdev(returns)
        annual_vol = vol * math.sqrt(365) if vol else None
        volume_avg_days = cfg.get("volume_average_days", 20)
        volume_multiple = cfg.get("volume_multiple", 0)
        volume_ok = True
        if volume_multiple:
            volume_ok = volumes[-1] >= mean(volumes[-volume_avg_days:]) * volume_multiple
        if prices[-1] > slow and fast > slow and momentum > 0 and annual_vol and volume_ok:
            candidates.append((symbol, momentum / annual_vol, annual_vol))
    candidates.sort(key=lambda x: x[1], reverse=True)
    selected = candidates[: cfg["max_positions"]]
    weights = {s: 0.0 for s in symbols}
    if not selected:
        return weights
    raw = {
        symbol: min(cfg["max_symbol_weight"], cfg["target_annual_volatility"] / annual_vol / len(selected))
        for symbol, _, annual_vol in selected
    }
    gross = sum(abs(w) for w in raw.values())
    if gross > cfg["max_gross_exposure"]:
        raw = {s: w * cfg["max_gross_exposure"] / gross for s, w in raw.items()}
    if peak and equity / peak - 1 <= -cfg["portfolio_drawdown_cut"]:
        raw = {s: w * cfg["drawdown_risk_scale"] for s, w in raw.items()}
    weights.update(raw)
    return weights


def nominal_weights(base_weights, cfg):
    return {s: w * leverage_for(s, cfg) for s, w in base_weights.items()}


def run_simulation(cfg):
    out_dir = result_dir(cfg)
    symbols, dates, by_symbol = load_market(cfg)
    start_index = max(cfg["slow_sma_days"] + 1, len(dates) - cfg["simulation_days"])
    equity = cfg["initial_equity_usdt"]
    peak = equity
    weights = {s: 0.0 for s in symbols}
    entry_ref = {}
    liquidation_price = {}
    rows = []
    trades = []
    liquidations = []
    open_positions = {}
    fees_paid = 0.0
    funding_paid = 0.0
    fee = fee_rate(cfg)

    for i in range(start_index, len(dates)):
        if (i - start_index) % cfg["rebalance_frequency_days"] == 0:
            base = calculate_base_weights(i - 1, dates, by_symbol, symbols, cfg, equity, peak)
            new_weights = nominal_weights(base, cfg)
            for s in symbols:
                old = weights.get(s, 0.0)
                new = new_weights.get(s, 0.0)
                prev_price = by_symbol[s][dates[i - 1]]["close"]
                if old <= 1e-12 and new > 1e-12:
                    entry_ref[s] = prev_price
                    liquidation_price[s] = prev_price * (1 - 1 / leverage_for(s, cfg))
                    open_positions[s] = {"symbol": s, "entry_date": dates[i - 1], "entry_price": prev_price}
                elif old > 1e-12 and new <= 1e-12 and s in open_positions:
                    trade = open_positions.pop(s)
                    trade["exit_date"] = dates[i - 1]
                    trade["exit_price"] = prev_price
                    trade["return"] = trade["exit_price"] / trade["entry_price"] - 1
                    trades.append(trade)
                    entry_ref.pop(s, None)
                    liquidation_price.pop(s, None)
                elif new > 1e-12 and abs(new - old) > 1e-9:
                    entry_ref[s] = prev_price
                    liquidation_price[s] = prev_price * (1 - 1 / leverage_for(s, cfg))
            turnover = sum(abs(new_weights[s] - weights.get(s, 0.0)) for s in symbols)
            cost = equity * turnover * fee
            fees_paid += cost
            equity -= cost
            weights = dict(new_weights)

        day = dates[i]
        liquidated = set()
        liquidation_loss = 0.0
        if cfg.get("liquidation_check"):
            for s, w in list(weights.items()):
                if w > 1e-12 and by_symbol[s][day]["low"] <= liquidation_price.get(s, -1):
                    loss = equity * w / leverage_for(s, cfg)
                    liquidation_loss += loss
                    liquidated.add(s)
                    liquidations.append({
                        "date": day,
                        "symbol": s,
                        "reference_price": entry_ref.get(s),
                        "liquidation_price": liquidation_price.get(s),
                        "day_low": by_symbol[s][day]["low"],
                        "loss": loss,
                    })

        gross = sum(abs(w) for w in weights.values())
        funding_cost = equity * gross * cfg.get("funding_daily_rate", 0)
        funding_paid += funding_cost
        day_return = 0.0
        for s in symbols:
            if s in liquidated:
                continue
            r = by_symbol[s][day]["close"] / by_symbol[s][dates[i - 1]]["close"] - 1
            day_return += weights.get(s, 0.0) * r
        equity = equity * (1 + day_return) - funding_cost - liquidation_loss

        for s in liquidated:
            weights[s] = 0.0
            entry_ref.pop(s, None)
            liquidation_price.pop(s, None)
            if s in open_positions:
                trade = open_positions.pop(s)
                trade["exit_date"] = day
                trade["exit_price"] = by_symbol[s][day]["low"]
                trade["return"] = -1 / leverage_for(s, cfg)
                trade["liquidated"] = True
                trades.append(trade)

        peak = max(peak, equity)
        rows.append({
            "date": day,
            "equity": round(equity, 4),
            "daily_return": day_return,
            "gross_exposure": gross,
            "drawdown": equity / peak - 1 if peak else 0,
        })

    for s, trade in open_positions.items():
        trade["exit_date"] = dates[-1]
        trade["exit_price"] = by_symbol[s][dates[-1]]["close"]
        trade["return"] = trade["exit_price"] / trade["entry_price"] - 1
        trade["open_at_end"] = True
        trades.append(trade)

    returns = [rows[i]["equity"] / rows[i - 1]["equity"] - 1 for i in range(1, len(rows)) if rows[i - 1]["equity"]]
    latest_base = calculate_base_weights(len(dates) - 1, dates, by_symbol, symbols, cfg, equity, peak)
    latest_weights = nominal_weights(latest_base, cfg)
    wins = sum(1 for trade in trades if trade.get("return", 0) > 0)
    summary = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "strategy_id": strategy_id(cfg),
        "display_name": cfg.get("display_name", strategy_id(cfg)),
        "start_date": rows[0]["date"],
        "end_date": rows[-1]["date"],
        "initial_equity_usdt": cfg["initial_equity_usdt"],
        "ending_equity_usdt": round(equity, 2),
        "pnl_usdt": round(equity - cfg["initial_equity_usdt"], 2),
        "return_pct": round((equity / cfg["initial_equity_usdt"] - 1) * 100, 2),
        "max_drawdown_pct": round(max_drawdown([r["equity"] for r in rows]) * 100, 2),
        "annualized_volatility_pct": round((stdev(returns) or 0) * math.sqrt(365) * 100, 2),
        "trade_count": len(trades),
        "win_rate_pct": round(wins / len(trades) * 100, 2) if trades else None,
        "fees_paid_usdt": round(fees_paid, 2),
        "funding_paid_usdt": round(funding_paid, 2),
        "liquidation_count": len(liquidations),
        "latest_weights": {s: round(w, 6) for s, w in latest_weights.items() if abs(w) > 1e-12},
    }
    with open(os.path.join(out_dir, "simulation_30d_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    with open(os.path.join(out_dir, "simulation_30d_equity.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "equity", "daily_return", "gross_exposure", "drawdown"])
        writer.writeheader()
        writer.writerows(rows)
    with open(os.path.join(out_dir, "simulation_30d_trades.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["symbol", "entry_date", "entry_price", "exit_date", "exit_price", "return", "open_at_end", "liquidated"])
        writer.writeheader()
        for trade in trades:
            writer.writerow({
                "symbol": trade["symbol"],
                "entry_date": trade["entry_date"],
                "entry_price": trade["entry_price"],
                "exit_date": trade["exit_date"],
                "exit_price": trade["exit_price"],
                "return": trade["return"],
                "open_at_end": trade.get("open_at_end", False),
                "liquidated": trade.get("liquidated", False),
            })
    return summary


def load_previous_targets(cfg):
    path = os.path.join(result_dir(cfg), "latest_targets.json")
    if os.path.exists(path):
        return load_json(path)
    return {}


def save_targets(cfg, weights):
    path = os.path.join(result_dir(cfg), "latest_targets.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(weights, f, indent=2)


def target_actions(previous, current):
    symbols = sorted(set(previous) | set(current))
    actions = []
    for s in symbols:
        old = float(previous.get(s, 0) or 0)
        new = float(current.get(s, 0) or 0)
        if abs(new - old) < 0.005:
            continue
        if old <= 1e-12 and new > 1e-12:
            verb = "新增"
        elif old > 1e-12 and new <= 1e-12:
            verb = "清仓"
        elif new > old:
            verb = "加仓"
        else:
            verb = "减仓"
        actions.append((verb, s, old, new))
    return actions


def format_signal(cfg):
    symbols, dates, by_symbol = load_market(cfg)
    state_path = os.path.join(result_dir(cfg), "simulation_30d_summary.json")
    state = load_json(state_path) if os.path.exists(state_path) else {
        "ending_equity_usdt": cfg["initial_equity_usdt"],
        "initial_equity_usdt": cfg["initial_equity_usdt"],
    }
    equity = state.get("ending_equity_usdt", cfg["initial_equity_usdt"])
    peak = max(equity, state.get("initial_equity_usdt", cfg["initial_equity_usdt"]))
    base = calculate_base_weights(len(dates) - 1, dates, by_symbol, symbols, cfg, equity, peak)
    weights = nominal_weights(base, cfg)
    active = {s: round(w, 6) for s, w in weights.items() if w > 1e-12}
    previous = load_previous_targets(cfg)
    actions = target_actions(previous, active)
    save_targets(cfg, active)
    rates, funding_error = fetch_funding_rates(cfg)

    lines = [
        f"LBank 策略信号: {cfg.get('display_name', strategy_id(cfg))}",
        f"日期: {dates[-1]}",
        f"纸账户: {equity:.2f} USDT",
        f"放量条件: {cfg.get('volume_multiple', 0)}x / 杠杆: {leverage_summary(cfg)}",
        "目标名义仓位:",
    ]
    if active:
        for symbol, weight in sorted(active.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- {symbol}: {weight * 100:.2f}%")
    else:
        lines.append("- 空仓")
    lines.append("动作:")
    if actions:
        for verb, symbol, old, new in actions:
            lines.append(f"- {verb} {symbol}: {old * 100:.2f}% -> {new * 100:.2f}%")
    else:
        lines.append("- 无变化")
    if cfg.get("funding_daily_rate", 0):
        if rates:
            lines.append("资金费率: 已读取 LBank 合约行情；纸账户仍按配置日费率估算")
        else:
            lines.append(f"资金费率: 实时读取失败，按配置日费率估算 ({funding_error})")
    else:
        lines.append("资金费率: 现货策略不计")
    return "\n".join(lines)


def leverage_summary(cfg):
    values = sorted(set([cfg.get("leverage_default", 1)] + list(cfg.get("leverage_by_symbol", {}).values())))
    return "/".join(f"{v}x" for v in values)


def format_review(cfg, weekly=False):
    summary = run_simulation(cfg)
    title = "周复盘" if weekly else "日复盘"
    lines = [
        f"LBank {title}: {summary['display_name']}",
        f"区间: {summary['start_date']} 至 {summary['end_date']}",
        f"初始: {summary['initial_equity_usdt']:.2f} USDT",
        f"当前: {summary['ending_equity_usdt']:.2f} USDT",
        f"盈亏: {summary['pnl_usdt']:+.2f} USDT ({summary['return_pct']:+.2f}%)",
        f"最大回撤: {summary['max_drawdown_pct']:.2f}%",
        f"交易数: {summary['trade_count']}",
        f"胜率: {summary['win_rate_pct'] if summary['win_rate_pct'] is not None else '暂无'}%",
        f"手续费: {summary['fees_paid_usdt']:.2f} USDT",
    ]
    if summary["funding_paid_usdt"]:
        lines.append(f"资金费率估算: {summary['funding_paid_usdt']:.2f} USDT")
    if summary["liquidation_count"]:
        lines.append(f"爆仓事件: {summary['liquidation_count']}")
    if summary["latest_weights"]:
        lines.append("当前目标名义仓位:")
        for symbol, weight in summary["latest_weights"].items():
            lines.append(f"- {symbol}: {weight * 100:.2f}%")
    else:
        lines.append("当前目标名义仓位: 空仓")
    return "\n".join(lines)


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
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as r:
        payload = json.loads(r.read().decode("utf-8"))
    return bool(payload.get("ok"))


def strategy_configs():
    if not os.path.isdir(STRATEGY_CONFIG_DIR):
        return [DEFAULT_CONFIG_PATH]
    return [
        os.path.join(STRATEGY_CONFIG_DIR, name)
        for name in sorted(os.listdir(STRATEGY_CONFIG_DIR))
        if name.endswith(".json")
    ]


def load_config_from_args(args):
    if len(args) >= 2:
        candidate = args[1]
        if os.path.exists(candidate):
            return load_json(candidate)
        path = os.path.join(STRATEGY_CONFIG_DIR, candidate if candidate.endswith(".json") else f"{candidate}.json")
        if os.path.exists(path):
            return load_json(path)
    return load_json(DEFAULT_CONFIG_PATH)


def run_all(command):
    messages = []
    for path in strategy_configs():
        cfg = load_json(path)
        if command == "signal-all":
            messages.append(format_signal(cfg))
        elif command == "review-all":
            messages.append(format_review(cfg))
        elif command == "weekly-all":
            messages.append(format_review(cfg, weekly=True))
        elif command == "simulate-all":
            messages.append(json.dumps(run_simulation(cfg), indent=2))
    text = "\n\n---\n\n".join(messages)
    if command in {"signal-all", "review-all", "weekly-all"}:
        send_telegram(text)
    else:
        print(text)


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "simulate"
    if command in {"signal-all", "review-all", "weekly-all", "simulate-all"}:
        run_all(command)
        return
    cfg = load_config_from_args(sys.argv[1:])
    if command == "simulate":
        print(json.dumps(run_simulation(cfg), indent=2))
    elif command == "signal":
        send_telegram(format_signal(cfg))
    elif command == "review":
        send_telegram(format_review(cfg))
    elif command == "weekly":
        send_telegram(format_review(cfg, weekly=True))
    else:
        raise SystemExit("usage: lbank_paper_trader.py [simulate|signal|review|weekly|simulate-all|signal-all|review-all|weekly-all] [strategy_id|config_path]")


if __name__ == "__main__":
    main()


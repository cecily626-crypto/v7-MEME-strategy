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
CONFIG_PATH = os.path.join(ROOT, "config", "lbank_paper.json")
RESULTS_DIR = os.path.join(ROOT, "results", "lbank_paper")
DATA_DIR = os.path.join(ROOT, "data", "lbank")
STATE_PATH = os.path.join(RESULTS_DIR, "paper_state.json")


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


def fetch_lbank_daily(symbol, cfg):
    os.makedirs(DATA_DIR, exist_ok=True)
    cache_path = os.path.join(DATA_DIR, f"{symbol}_day1.csv")
    start_ts = int(time.time()) - cfg["lookback_days"] * 86400
    params = urllib.parse.urlencode({
        "symbol": symbol,
        "size": min(2000, cfg["lookback_days"]),
        "type": cfg["timeframe"],
        "time": start_ts,
    })
    url = f"{cfg['lbank_spot_base_url']}/v2/kline.do?{params}"
    payload = http_json(url)
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
            rate = item.get("prePositionFeeRate")
            if symbol and rate not in (None, ""):
                rates[symbol] = float(rate)
        return rates, None
    except Exception as exc:
        return {}, str(exc)


def load_market(cfg):
    data = {symbol: fetch_lbank_daily(symbol, cfg) for symbol in cfg["symbols"]}
    data = {s: rows for s, rows in data.items() if len(rows) > cfg["slow_sma_days"] + 5}
    close = {s: {r["date"]: r["close"] for r in rows} for s, rows in data.items()}
    dates = sorted(set.intersection(*(set(v) for v in close.values())))
    return list(data.keys()), dates, close


def calculate_weights(index, dates, close, symbols, cfg, equity, peak):
    if index < cfg["slow_sma_days"] + 1:
        return {s: 0.0 for s in symbols}
    candidates = []
    for symbol in symbols:
        prices = [close[symbol][d] for d in dates[: index + 1]]
        fast = mean(prices[-cfg["fast_sma_days"]:])
        slow = mean(prices[-cfg["slow_sma_days"]:])
        momentum = prices[-1] / prices[-cfg["momentum_days"]] - 1
        returns = [prices[i] / prices[i - 1] - 1 for i in range(len(prices) - cfg["volatility_days"], len(prices))]
        vol = stdev(returns)
        annual_vol = vol * math.sqrt(365) if vol else None
        if prices[-1] > slow and fast > slow and momentum > 0 and annual_vol:
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


def run_simulation(cfg):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    symbols, dates, close = load_market(cfg)
    start_index = max(cfg["slow_sma_days"] + 1, len(dates) - cfg["simulation_days"])
    equity = cfg["initial_equity_usdt"]
    peak = equity
    weights = {s: 0.0 for s in symbols}
    fee_key = "maker_fee_bps" if cfg.get("paper_fee_mode") == "maker" else "taker_fee_bps"
    fee = (cfg.get(fee_key, cfg.get("fee_bps", 0)) + cfg["slippage_bps"]) / 10000
    rows = []
    trades = []
    open_positions = {}

    for i in range(start_index, len(dates)):
        if (i - start_index) % cfg["rebalance_frequency_days"] == 0:
            new_weights = calculate_weights(i - 1, dates, close, symbols, cfg, equity, peak)
            for s in symbols:
                old = weights.get(s, 0.0)
                new = new_weights.get(s, 0.0)
                if old <= 1e-12 and new > 1e-12:
                    open_positions[s] = {"symbol": s, "entry_date": dates[i - 1], "entry_price": close[s][dates[i - 1]]}
                elif old > 1e-12 and new <= 1e-12 and s in open_positions:
                    trade = open_positions.pop(s)
                    trade["exit_date"] = dates[i - 1]
                    trade["exit_price"] = close[s][dates[i - 1]]
                    trade["return"] = trade["exit_price"] / trade["entry_price"] - 1
                    trades.append(trade)
            turnover = sum(abs(new_weights[s] - weights.get(s, 0.0)) for s in symbols)
            equity *= 1 - turnover * fee
            weights = dict(new_weights)

        day_return = sum(weights.get(s, 0.0) * (close[s][dates[i]] / close[s][dates[i - 1]] - 1) for s in symbols)
        equity *= 1 + day_return
        peak = max(peak, equity)
        rows.append({
            "date": dates[i],
            "equity": round(equity, 4),
            "daily_return": day_return,
            "gross_exposure": sum(abs(w) for w in weights.values()),
            "drawdown": equity / peak - 1,
        })

    for s, trade in open_positions.items():
        trade["exit_date"] = dates[-1]
        trade["exit_price"] = close[s][dates[-1]]
        trade["return"] = trade["exit_price"] / trade["entry_price"] - 1
        trade["open_at_end"] = True
        trades.append(trade)

    returns = [rows[i]["equity"] / rows[i - 1]["equity"] - 1 for i in range(1, len(rows))]
    summary = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "long_only_lbank_paper",
        "start_date": rows[0]["date"],
        "end_date": rows[-1]["date"],
        "initial_equity_usdt": cfg["initial_equity_usdt"],
        "ending_equity_usdt": round(equity, 2),
        "pnl_usdt": round(equity - cfg["initial_equity_usdt"], 2),
        "return_pct": round((equity / cfg["initial_equity_usdt"] - 1) * 100, 2),
        "max_drawdown_pct": round(max_drawdown([r["equity"] for r in rows]) * 100, 2),
        "annualized_volatility_pct": round((stdev(returns) or 0) * math.sqrt(365) * 100, 2),
        "trade_count": len(trades),
        "latest_weights": {s: round(w, 6) for s, w in weights.items() if abs(w) > 1e-12},
    }
    with open(os.path.join(RESULTS_DIR, "simulation_30d_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    with open(os.path.join(RESULTS_DIR, "simulation_30d_equity.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "equity", "daily_return", "gross_exposure", "drawdown"])
        writer.writeheader()
        writer.writerows(rows)
    with open(os.path.join(RESULTS_DIR, "simulation_30d_trades.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["symbol", "entry_date", "entry_price", "exit_date", "exit_price", "return", "open_at_end"])
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
            })
    return summary


def format_signal(cfg):
    symbols, dates, close = load_market(cfg)
    state = load_json(STATE_PATH) if os.path.exists(STATE_PATH) else {
        "equity": cfg["initial_equity_usdt"],
        "peak": cfg["initial_equity_usdt"],
        "weights": {s: 0.0 for s in symbols},
    }
    weights = calculate_weights(len(dates) - 1, dates, close, symbols, cfg, state["equity"], state["peak"])
    rates, funding_error = fetch_funding_rates(cfg)
    lines = [
        "LBank 做多策略信号",
        f"日期: {dates[-1]}",
        f"模拟账户: {state['equity']:.2f} USDT",
        "目标仓位:",
    ]
    active = [(s, w) for s, w in weights.items() if w > 0]
    if active:
        for symbol, weight in sorted(active, key=lambda x: x[1], reverse=True):
            lines.append(f"- {symbol}: {weight * 100:.2f}%")
    else:
        lines.append("- 空仓")
    if rates:
        lines.append("资金费率: 已读取 LBank 合约行情")
    else:
        lines.append(f"资金费率: 暂不可用，纸面账户按 0 计算 ({funding_error})")
    lines.append("方向: 只做多；做空模块后续单独开发")
    return "\n".join(lines)


def format_review(cfg):
    summary = run_simulation(cfg)
    lines = [
        "LBank 前一日复盘 / 30日纸面账户",
        f"区间: {summary['start_date']} 至 {summary['end_date']}",
        f"初始: {summary['initial_equity_usdt']:.2f} USDT",
        f"当前: {summary['ending_equity_usdt']:.2f} USDT",
        f"盈亏: {summary['pnl_usdt']:+.2f} USDT ({summary['return_pct']:+.2f}%)",
        f"最大回撤: {summary['max_drawdown_pct']:.2f}%",
        f"30日交易数: {summary['trade_count']}",
    ]
    if summary["latest_weights"]:
        lines.append("当前持仓:")
        for symbol, weight in summary["latest_weights"].items():
            lines.append(f"- {symbol}: {weight * 100:.2f}%")
    else:
        lines.append("当前持仓: 空仓")
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


def main():
    cfg = load_json(CONFIG_PATH)
    command = sys.argv[1] if len(sys.argv) > 1 else "simulate"
    if command == "simulate":
        print(json.dumps(run_simulation(cfg), indent=2))
    elif command == "signal":
        send_telegram(format_signal(cfg))
    elif command == "review":
        send_telegram(format_review(cfg))
    else:
        raise SystemExit("usage: lbank_paper_trader.py [simulate|signal|review]")


if __name__ == "__main__":
    main()

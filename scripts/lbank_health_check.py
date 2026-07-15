#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RUNNER_DIR = os.path.expanduser("~/lbank-strategy-runner")
STATE_DIR = os.path.join(DEFAULT_RUNNER_DIR, "state")
STATE_PATH = os.path.join(STATE_DIR, "health_check_state.json")


@dataclass
class ExpectedRun:
    command: str
    display_name: str
    max_age_hours: float
    requires_telegram: bool = True


EXPECTED_RUNS = [
    ExpectedRun("review-all", "每日复盘", 30),
    ExpectedRun("signal-all", "晚间信号", 30),
    ExpectedRun("mtf-long-notify", "多周期小时观察", 4.5, requires_telegram=False),
    ExpectedRun("weekly-all", "周复盘", 24 * 8),
]

START_RE = re.compile(r"^===== (?P<ts>.+?) START (?P<command>.+?) =====$")
END_RE = re.compile(r"^===== (?P<ts>.+?) END (?P<command>.+?) status=(?P<status>-?\d+) =====$")


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


def parse_log_time(value):
    # Runner logs use strings like "2026-07-13 01:47:40 EDT".
    base = value.rsplit(" ", 1)[0]
    dt = datetime.strptime(base, "%Y-%m-%d %H:%M:%S")
    return dt.astimezone()


def read_log_state(log_path):
    if not os.path.exists(log_path):
        return [], None
    blocks = []
    current = None
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            start = START_RE.match(line)
            if start:
                current = {
                    "command": start.group("command"),
                    "start_ts": parse_log_time(start.group("ts")),
                    "lines": [],
                    "end_ts": None,
                    "status": None,
                }
                continue
            if current is not None:
                end = END_RE.match(line)
                if end:
                    current["end_ts"] = parse_log_time(end.group("ts"))
                    current["status"] = int(end.group("status"))
                    blocks.append(current)
                    current = None
                else:
                    current["lines"].append(line)
    return blocks, current


def read_blocks(log_path):
    return read_log_state(log_path)[0]


def last_success(expected, log_dir):
    command = expected.command
    path = os.path.join(log_dir, f"{command}.log")
    successes = []
    last_block = None
    blocks, current = read_log_state(path)
    for block in blocks:
        last_block = block
        sent = any("Telegram sent successfully" in line for line in block["lines"])
        if block["status"] == 0 and (sent or not expected.requires_telegram):
            successes.append(block)
    return {
        "path": path,
        "last_block": last_block,
        "last_success": successes[-1] if successes else None,
        "in_progress": current,
    }


def format_age(seconds):
    if seconds < 3600:
        return f"{seconds / 60:.0f}分钟"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}小时"
    return f"{seconds / 86400:.1f}天"


def send_telegram(text):
    load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(text)
        print("Telegram not sent: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing.")
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


def load_state():
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, sort_keys=True)
    except Exception as exc:
        print(f"Health check state not saved: {exc}")


def build_report(log_dir):
    now = datetime.now().astimezone()
    problems = []
    ok_lines = []
    for expected in EXPECTED_RUNS:
        info = last_success(expected, log_dir)
        success = info["last_success"]
        last = info["last_block"]
        in_progress = info["in_progress"]
        if in_progress:
            running_seconds = (now - in_progress["start_ts"]).total_seconds()
            max_running_seconds = max(expected.max_age_hours, 4) * 3600
            if running_seconds <= max_running_seconds:
                ok_lines.append(f"- {expected.display_name}: 正在运行，已运行 {format_age(running_seconds)}")
                continue
            problems.append(
                f"- {expected.display_name}: 任务已运行 {format_age(running_seconds)} 仍未结束；日志 {info['path']}"
            )
            continue
        if not success:
            detail = "从未成功发送"
            if last:
                detail = f"最近一次退出码 {last['status']}"
            problems.append(f"- {expected.display_name}: {detail}; 日志 {info['path']}")
            continue
        if last and last["status"] != 0 and last["end_ts"] >= success["end_ts"]:
            problems.append(
                f"- {expected.display_name}: 最近一次运行失败，退出码 {last['status']}；"
                f"最近成功在 {success['end_ts'].strftime('%Y-%m-%d %H:%M:%S')}"
            )
            continue
        age_seconds = (now - success["end_ts"]).total_seconds()
        max_age_seconds = expected.max_age_hours * 3600
        if age_seconds > max_age_seconds:
            problems.append(
                f"- {expected.display_name}: 最近成功在 {success['end_ts'].strftime('%Y-%m-%d %H:%M:%S')}, "
                f"距今 {format_age(age_seconds)}, 超过阈值 {expected.max_age_hours:g}小时"
            )
        else:
            ok_lines.append(f"- {expected.display_name}: 最近成功 {format_age(age_seconds)}前")
    return problems, ok_lines


def should_alert(problems, cooldown_hours):
    signature = hashlib.sha256("\n".join(problems).encode("utf-8")).hexdigest()
    state = load_state()
    now = time.time()
    last_signature = state.get("last_signature")
    last_alert_at = float(state.get("last_alert_at", 0) or 0)
    if signature == last_signature and now - last_alert_at < cooldown_hours * 3600:
        return False, signature
    return True, signature


def main():
    parser = argparse.ArgumentParser(description="Check LBank launchd workflow health.")
    parser.add_argument("--log-dir", default=os.path.join(DEFAULT_RUNNER_DIR, "logs"))
    parser.add_argument("--cooldown-hours", type=float, default=6)
    parser.add_argument("--send-ok", action="store_true", help="Send Telegram even when all checks are healthy.")
    args = parser.parse_args()

    problems, ok_lines = build_report(args.log_dir)
    now = datetime.now(timezone.utc).astimezone()
    if problems:
        should_send, signature = should_alert(problems, args.cooldown_hours)
        text = "\n".join([
            "LBank 策略健康检查告警",
            f"时间: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            "",
            "异常:",
            *problems,
            "",
            "最近正常项:",
            *(ok_lines or ["- 无"]),
        ])
        if should_send:
            sent = send_telegram(text)
            save_state({"last_signature": signature, "last_alert_at": time.time(), "last_sent": sent})
        else:
            print("Health check unhealthy; duplicate alert suppressed by cooldown.")
            print(text)
        return 1

    text = "\n".join([
        "LBank 策略健康检查正常",
        f"时间: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        *ok_lines,
    ])
    print(text)
    save_state({"last_signature": "", "last_alert_at": 0, "last_ok_at": time.time()})
    if args.send_ok:
        return 0 if send_telegram(text) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""关键事件时间线 + 复盘。

- list: 列出关系档案里的关键事件
- review: 提取某事件前后 N 条消息上下文，供 LLM 复盘（背景/双方反应/后续/关系变化）

用法:
    python3 events.py list --profile data/profile.json
    python3 events.py review --datetime "2026-11-03 20:00" --input data/messages.json \
        --before 20 --after 20
    python3 events.py review --event-id 0 --profile data/profile.json \
        --input data/messages.json --before 20 --after 20
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys


def load(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_dt(s: str) -> int:
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return int(datetime.datetime.strptime(s, fmt).timestamp())
        except ValueError:
            continue
    sys.exit(f"无法解析时间: {s}")


def list_events(profile: dict) -> None:
    events = profile.get("key_events", [])
    if not events:
        print("（暂无关键事件）")
        return
    for i, e in enumerate(events):
        print(f"[{i}] {e.get('datetime')}  {e.get('type', '')}")
        if e.get("evidence"):
            print(f"    证据: {e['evidence'][:80]}")
        if e.get("outcome"):
            print(f"    结果: {e['outcome'][:80]}")


def review(messages: list[dict], ts: int, before: int, after: int) -> list[dict]:
    """提取时间戳 ts 前后各 before/after 条消息。"""
    msgs = sorted(messages, key=lambda m: (m.get("timestamp", 0), m.get("source_file", "")))
    before_msgs = [m for m in msgs if m.get("timestamp", 0) <= ts][-before:]
    after_msgs = [m for m in msgs if m.get("timestamp", 0) > ts][:after]
    return before_msgs, after_msgs


def fmt_msg(m: dict) -> str:
    return f"{m.get('datetime', '')} {m.get('sender_name', m.get('sender', ''))}：{m.get('content', '')}"


def main():
    ap = argparse.ArgumentParser(description="关键事件时间线 + 复盘")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="列出关键事件")
    p_list.add_argument("--profile", default="data/profile.json")

    p_rev = sub.add_parser("review", help="复盘事件（提取前后上下文）")
    p_rev.add_argument("--input", required=True, help="结构化消息 JSON")
    g = p_rev.add_mutually_exclusive_group(required=True)
    g.add_argument("--datetime", help="事件时间")
    g.add_argument("--event-id", type=int, help="事件在档案里的序号（配合 --profile）")
    p_rev.add_argument("--profile", default="data/profile.json")
    p_rev.add_argument("--before", type=int, default=20)
    p_rev.add_argument("--after", type=int, default=20)

    args = ap.parse_args()

    if args.cmd == "list":
        list_events(load(args.profile))

    elif args.cmd == "review":
        payload = load(args.input)
        messages = payload.get("messages", [])
        if not messages:
            sys.exit(f"消息为空: {args.input}")

        ts = None
        label = ""
        if args.event_id is not None:
            profile = load(args.profile)
            events = profile.get("key_events", [])
            if not (0 <= args.event_id < len(events)):
                sys.exit(f"事件序号 {args.event_id} 不存在（共 {len(events)} 条）")
            e = events[args.event_id]
            ts = parse_dt(e.get("datetime", ""))
            label = f"{e.get('type', '')} @ {e.get('datetime')}"
        else:
            ts = parse_dt(args.datetime)
            label = args.datetime

        before_msgs, after_msgs = review(messages, ts, args.before, args.after)
        print(f"=== 复盘事件: {label} ===")
        print(f"\n--- 事件前 {len(before_msgs)} 条 ---")
        for m in before_msgs:
            print("  " + fmt_msg(m))
        print(f"\n--- 事件后 {len(after_msgs)} 条 ---")
        for m in after_msgs:
            print("  " + fmt_msg(m))


if __name__ == "__main__":
    main()

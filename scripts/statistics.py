#!/usr/bin/env python3
"""基于结构化消息 JSON 计算客观统计指标。

只算客观事实（数量、频率、时间间隔、消息类型分布），不做主观判断
（如「谁更喜欢对方」）。主观分析交给 LLM（见 SKILL.md）。

用法:
    python3 statistics.py --input data/messages.json --output data/stats.json
"""
from __future__ import annotations

import argparse
import collections
import datetime
import json
import os

# 深夜时段（小时区间，含起点）
NIGHT_START, NIGHT_END = 22, 6
# 判断「谁开启话题」的间隔阈值（小时）：超过该间隔后的首条消息视为新话题发起者
INITIATE_GAP_HOURS = 4
# 对话中断阈值（小时）
BREAK_GAP_HOURS = 24


def _count_utf8_len(s: str) -> int:
    return len(s or "")


def compute(messages: list[dict]) -> dict:
    return _compute(messages)


def _compute(messages: list[dict]) -> dict:
    if not messages:
        return {"message_count": 0}

    senders = sorted({m["sender"] for m in messages})
    other = senders  # 双方
    n = len(messages)

    # 1. 双方消息数量
    by_sender = collections.Counter(m["sender"] for m in messages)

    # 2. 每日频率
    daily = collections.Counter(m["datetime"][:10] for m in messages)

    # 3. 消息类型分布
    by_type = collections.Counter(m["message_type"] for m in messages)

    # 4. 谁开启话题（间隔 > INITIATE_GAP_HOURS 后的首条消息的发送者）
    initiator = collections.Counter()
    prev_ts = None
    for m in messages:
        if prev_ts is None or (m["timestamp"] - prev_ts) > INITIATE_GAP_HOURS * 3600:
            initiator[m["sender"]] += 1
        prev_ts = m["timestamp"]

    # 5. 平均回复时间：A 的消息到下一条 B 的消息的时间差
    reply_deltas = collections.defaultdict(list)
    for i in range(n - 1):
        cur, nxt = messages[i], messages[i + 1]
        if cur["sender"] != nxt["sender"]:
            delta = nxt["timestamp"] - cur["timestamp"]
            # 忽略超过 24h 的（不算即时回复）
            if 0 <= delta <= 24 * 3600:
                reply_deltas[cur["sender"]].append(delta)

    reply_avg = {}
    for s, ds in reply_deltas.items():
        if ds:
            reply_avg[s] = round(sum(ds) / len(ds) / 60, 1)  # 分钟

    # 6. 深夜聊天（22:00 - 06:00）
    night = collections.Counter()
    for m in messages:
        h = int(m["datetime"][11:13])
        if h >= NIGHT_START or h < NIGHT_END:
            night[m["sender"]] += 1

    # 7. 对话中断（间隔 > BREAK_GAP_HOURS）
    breaks = []
    for i in range(1, n):
        gap_h = (messages[i]["timestamp"] - messages[i - 1]["timestamp"]) / 3600
        if gap_h > BREAK_GAP_HOURS:
            breaks.append({
                "from": messages[i - 1]["datetime"],
                "to": messages[i]["datetime"],
                "gap_hours": round(gap_h, 1),
            })

    # 8. 文本消息长度（每方平均）
    text_lens = collections.defaultdict(list)
    for m in messages:
        if m["message_type"] == "text":
            text_lens[m["sender"]].append(_count_utf8_len(m["content"]))
    text_avg = {s: round(sum(v) / len(v), 1) for s, v in text_lens.items() if v}

    # 9. 非文本消息占比（每方）
    nontext = collections.Counter()
    for m in messages:
        if m["message_type"] != "text":
            nontext[m["sender"]] += 1

    return {
        "message_count": n,
        "time_range": {
            "first": messages[0]["datetime"],
            "last": messages[-1]["datetime"],
            "days": (messages[-1]["timestamp"] - messages[0]["timestamp"]) // 86400 + 1,
        },
        "messages_by_sender": dict(by_sender),
        "messages_by_type": dict(by_type),
        "daily_frequency": dict(sorted(daily.items())),
        "topic_initiations": dict(initiator),
        "avg_reply_minutes": reply_avg,
        "night_messages": dict(night),
        "breaks": breaks,
        "avg_text_length": text_avg,
        "non_text_count": dict(nontext),
        "recent_windows": _recent_windows(messages),
    }


def _recent_windows(messages: list[dict]) -> dict:
    """最近 7 天 / 30 天窗口对比（供进度追踪）。"""
    if not messages:
        return {}
    last_ts = max(m["timestamp"] for m in messages)
    out = {}
    for days in (7, 30):
        cutoff = last_ts - days * 86400
        win = [m for m in messages if m["timestamp"] >= cutoff]
        by_sender = collections.Counter(m["sender"] for m in win)
        night = sum(1 for m in win if int(m["datetime"][11:13]) >= 22 or int(m["datetime"][11:13]) < 6)
        nontext = sum(1 for m in win if m["message_type"] != "text")
        # 窗口内谁开启话题
        init = collections.Counter()
        prev = None
        for m in win:
            if prev is None or (m["timestamp"] - prev) > INITIATE_GAP_HOURS * 3600:
                init[m["sender"]] += 1
            prev = m["timestamp"]
        out[f"recent_{days}d"] = {
            "message_count": len(win),
            "messages_per_day": round(len(win) / days, 1),
            "by_sender": dict(by_sender),
            "topic_initiations": dict(init),
            "night_count": night,
            "non_text_ratio": round(nontext / len(win), 3) if win else 0,
        }
    return out


def main():
    ap = argparse.ArgumentParser(description="计算聊天客观统计")
    ap.add_argument("--input", required=True, help="结构化消息 JSON 路径")
    ap.add_argument("--output", default="data/stats.json")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        payload = json.load(f)
    messages = payload.get("messages", payload if isinstance(payload, list) else [])

    stats = compute(messages)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"✅ 统计完成 -> {args.output}")
    print(f"   总消息 {stats.get('message_count')} 条，"
          f"双方各 {stats.get('messages_by_sender')}")


if __name__ == "__main__":
    main()

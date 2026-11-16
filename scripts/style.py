#!/usr/bin/env python3
"""聊天风格客观指标 —— 建立个人聊天风格档案的数据基础。

从结构化消息中提取可量化风格特征（供 LLM 解读、写入 profile 的 chat_style）：
- 平均文本长度
- 表情/图片占比
- 标点习惯（问号/感叹号/句号）
- 高频短语（2~3 字 n-gram，用于发现口头禅）
- 消息类型分布
- 时段分布（深夜/上午/下午/晚上）

用法:
    python3 style.py analyze --input data/messages.json --output data/style.json
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re


def _is_meaningful(phrase: str) -> bool:
    if not phrase:
        return False
    if re.search(r"[\s，。！？、：；（）【】《》“”‘’.,!?:;()\[\]@#]", phrase):
        return False
    return True


def analyze(messages: list[dict]) -> dict:
    senders = sorted({m["sender"] for m in messages if m["sender"]})
    result = {}
    for s in senders:
        msgs = [m for m in messages if m["sender"] == s]
        text_msgs = [m for m in msgs if m["message_type"] == "text"]
        n = len(msgs)

        # 平均文本长度
        lens = [len(m["content"]) for m in text_msgs if m.get("content")]
        avg_len = round(sum(lens) / len(lens), 1) if lens else 0

        # 表情/图片占比
        emoji = sum(1 for m in msgs if m["message_type"] == "emoji")
        image = sum(1 for m in msgs if m["message_type"] == "image")

        # 标点习惯（每 100 条文本消息里的标点次数）
        texts = "".join(m["content"] for m in text_msgs if m.get("content"))
        n_text = len(text_msgs) or 1
        punct = {
            "问号_每百条": round(texts.count("？") / n_text * 100, 1),
            "感叹号_每百条": round(texts.count("！") / n_text * 100, 1),
            "句号_每百条": round(texts.count("。") / n_text * 100, 1),
        }

        # 高频短语（2~3 字）
        grams = collections.Counter()
        for m in text_msgs:
            c = m.get("content", "")
            for ln in (2, 3):
                for i in range(len(c) - ln + 1):
                    g = c[i:i + ln]
                    if _is_meaningful(g):
                        grams[g] += 1
        # 过滤掉只出现 1 次的，取 top
        common = [g for g, cnt in grams.most_common(30) if cnt >= 3]

        # 时段分布
        slot = collections.Counter()
        for m in msgs:
            h = int(m["datetime"][11:13]) if len(m.get("datetime", "")) >= 13 else -1
            if 6 <= h < 12:
                slot["上午"] += 1
            elif 12 <= h < 18:
                slot["下午"] += 1
            elif 18 <= h < 22:
                slot["晚上"] += 1
            else:
                slot["深夜"] += 1

        # 类型分布
        types = collections.Counter(m["message_type"] for m in msgs)

        result[s] = {
            "message_count": n,
            "avg_text_length": avg_len,
            "emoji_ratio": round(emoji / n, 3) if n else 0,
            "image_ratio": round(image / n, 3) if n else 0,
            "punct_per_100_text": punct,
            "common_phrases": common,
            "time_slots": dict(slot),
            "message_types": dict(types),
        }
    return result


def main():
    ap = argparse.ArgumentParser(description="聊天风格客观指标")
    ap.add_argument("--input", required=True, help="结构化消息 JSON")
    ap.add_argument("--output", default="data/style.json")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        payload = json.load(f)
    messages = payload.get("messages", [])

    style = analyze(messages)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(style, f, ensure_ascii=False, indent=2)

    for s, st in style.items():
        print(f"[{s}] 平均长度 {st['avg_text_length']} 字，"
              f"表情占比 {st['emoji_ratio']*100:.0f}%，"
              f"高频词: {st['common_phrases'][:6]}")
    print(f"✅ 风格指标 -> {args.output}")


if __name__ == "__main__":
    main()

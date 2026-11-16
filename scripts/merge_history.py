#!/usr/bin/env python3
"""增量合并聊天记录 + 历史对比。

把新提取的消息与历史全量消息合并（按 source_file+source_reference 去重），
输出合并结果和「本次新增」摘要，供后续分析判断关系是否变化。

用法:
    python3 merge_history.py --input data/messages.json --history data/history/messages.json \
        --output data/history/messages.json --progress data/progress.json
"""
from __future__ import annotations

import argparse
import json
import os


def load(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _key(m: dict) -> str:
    return f"{m.get('source_file', '')}|{m.get('source_reference', '')}"


def merge(new_messages: list[dict], old_messages: list[dict]) -> tuple[list[dict], list[dict]]:
    old_keys = {_key(m) for m in old_messages}
    added = [m for m in new_messages if _key(m) not in old_keys]
    merged = old_messages + added
    merged.sort(key=lambda m: (m.get("timestamp", 0), m.get("source_file", "")))
    return merged, added


def main():
    ap = argparse.ArgumentParser(description="增量合并聊天记录")
    ap.add_argument("--input", required=True, help="新提取的消息 JSON")
    ap.add_argument("--history", default="data/history/messages.json", help="历史全量 JSON")
    ap.add_argument("--output", default="data/history/messages.json", help="合并后输出路径")
    ap.add_argument("--progress", default="data/progress.json", help="本次增量摘要")
    args = ap.parse_args()

    new_payload = load(args.input)
    old_payload = load(args.history)
    new_msgs = new_payload.get("messages", [])
    old_msgs = old_payload.get("messages", [])

    merged, added = merge(new_msgs, old_msgs)

    # 写合并结果
    out_payload = dict(new_payload)
    out_payload["messages"] = merged
    out_payload["message_count"] = len(merged)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out_payload, f, ensure_ascii=False, indent=2)

    # 写增量摘要
    progress = {
        "new_count": len(added),
        "total_count": len(merged),
        "new_messages": added[:500],  # 截断，避免过大
        "new_first_time": added[0]["datetime"] if added else None,
        "new_last_time": added[-1]["datetime"] if added else None,
        "history_had": len(old_msgs),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.progress)), exist_ok=True)
    with open(args.progress, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

    print(f"✅ 合并完成：历史 {len(old_msgs)} 条 + 本次新增 {len(added)} 条 = {len(merged)} 条")
    if added:
        print(f"   新增时间范围: {added[0]['datetime']} ~ {added[-1]['datetime']}")
    print(f"   增量摘要 -> {args.progress}")


if __name__ == "__main__":
    main()

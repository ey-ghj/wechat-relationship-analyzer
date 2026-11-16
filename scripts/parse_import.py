#!/usr/bin/env python3
"""从导出的聊天记录文件（TXT/CSV/JSON/HTML/OCR 文本）导入并归一化为统一结构。

支持常见微信/QQ 导出格式，尽力自动识别。识别不出时保留原文并标记 sender 为 unknown。

用法:
    python3 parse_import.py --input chat_export.txt --output data/messages.json \
        --self "我" --target "对方"
    python3 parse_import.py --input a.txt --input b.csv --output data/messages.json
"""
from __future__ import annotations

import argparse
import csv
import datetime
import html as html_mod
import json
import os
import re

# 常见「时间 发送人: 内容」行格式
LINE_PATTERNS = [
    # 2024-01-01 10:00:00 张三: 你好
    re.compile(r"^(\d{4}[-/]\d{1,2}[-/]\d{1,2}[ T]\d{1,2}:\d{2}(?::\d{2})?)\s+([^:：]{1,30})[：:]\s*(.*)$"),
    # [2024-01-01 10:00:00] 张三: 你好
    re.compile(r"^\[(\d{4}[-/]\d{1,2}[-/]\d{1,2}[ T]\d{1,2}:\d{2}(?::\d{2})?)\]\s*([^:：]{1,30})[：:]\s*(.*)$"),
    # 张三 2024-01-01 10:00:00 你好
    re.compile(r"^([^:：]{1,30})\s+(\d{4}[-/]\d{1,2}[-/]\d{1,2}[ T]\d{1,2}:\d{2}(?::\d{2})?)\s+(.*)$"),
]


def _parse_datetime(s: str) -> int | None:
    s = s.replace("/", "-")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return int(datetime.datetime.strptime(s, fmt).timestamp())
        except ValueError:
            continue
    return None


def _clean(s: str) -> str:
    return html_mod.unescape(s).strip()


def parse_txt(text: str, self_name: str, target_name: str) -> list[dict]:
    msgs = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        matched = False
        for pat in LINE_PATTERNS:
            m = pat.match(line)
            if m:
                ts = _parse_datetime(m.group(1))
                sender_raw = _clean(m.group(2))
                content = _clean(m.group(3) if len(m.groups()) >= 3 else "")
                sender = self_name if sender_raw in (self_name, "我") else (target_name if sender_raw == target_name else sender_raw)
                msgs.append(_mk(ts, sender, "text", content, "txt", line[:120]))
                matched = True
                break
        if not matched:
            # 无匹配，作为 continuation 或未知消息，附到上一条
            if msgs and msgs[-1]["message_type"] == "text":
                msgs[-1]["content"] += "\n" + line
            else:
                msgs.append(_mk(None, "unknown", "text", line, "txt", line[:120]))
    return msgs


def parse_csv(path: str) -> list[dict]:
    msgs = []
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 尝试常见列名
            ts_col = next((k for k in row if k.lower() in ("time", "timestamp", "时间", "datetime")), None)
            sender_col = next((k for k in row if k.lower() in ("sender", "name", "发送者", "发送人", "昵称")), None)
            content_col = next((k for k in row if k.lower() in ("content", "message", "text", "内容", "消息")), None)
            if not content_col:
                continue
            ts = _parse_datetime(row[ts_col]) if ts_col else None
            sender = row.get(sender_col, "unknown") or "unknown"
            content = row.get(content_col, "")
            msgs.append(_mk(ts, sender, "text", _clean(content), "csv", json.dumps(row, ensure_ascii=False)[:120]))
    return msgs


def parse_json(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "messages" in data:
        data = data["messages"]
    if not isinstance(data, list):
        return []
    out = []
    for m in data:
        if not isinstance(m, dict):
            continue
        ts = m.get("timestamp") or (_parse_datetime(m["datetime"]) if m.get("datetime") else None)
        out.append(_mk(
            ts,
            m.get("sender") or m.get("sender_name") or "unknown",
            m.get("message_type", "text"),
            str(m.get("content", "")),
            "json",
            m.get("source_reference", "")[:120],
        ))
    return out


def _mk(ts, sender, mtype, content, source_file, source_ref):
    return {
        "timestamp": ts or 0,
        "datetime": datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "",
        "sender": sender,
        "sender_name": sender,
        "receiver": "",
        "receiver_name": "",
        "message_type": mtype,
        "content": content,
        "source_file": source_file,
        "source_reference": source_ref,
    }


def main():
    ap = argparse.ArgumentParser(description="导入导出的聊天记录文件")
    ap.add_argument("--input", action="append", required=True, help="输入文件（可多次）")
    ap.add_argument("--output", default="data/messages.json")
    ap.add_argument("--self", default="我", help="自己的显示名")
    ap.add_argument("--target", default="对方", help="对方的显示名")
    args = ap.parse_args()

    all_msgs = []
    for path in args.input:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".json":
            msgs = parse_json(path)
        elif ext == ".csv":
            msgs = parse_csv(path)
        elif ext in (".html", ".htm"):
            with open(path, encoding="utf-8", errors="replace") as f:
                text = html_mod.unescape(re.sub(r"<[^>]+>", "\n", f.read()))
            msgs = parse_txt(text, args.self, args.target)
        else:
            with open(path, encoding="utf-8", errors="replace") as f:
                msgs = parse_txt(f.read(), args.self, args.target)
        all_msgs.extend(msgs)

    all_msgs.sort(key=lambda m: (m["timestamp"], m["source_file"]))
    payload = {
        "message_count": len(all_msgs),
        "extracted_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "messages": all_msgs,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"✅ 导入 {len(all_msgs)} 条消息 -> {args.output}")


if __name__ == "__main__":
    main()

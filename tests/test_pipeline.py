#!/usr/bin/env python3
"""测试核心脚本逻辑（使用合成数据，不含真实聊天记录）。

运行: python3 tests/test_pipeline.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import merge_history  # noqa: E402
import parse_import  # noqa: E402
import statistics  # noqa: E402


def test_parse_txt():
    text = (
        "2024-01-01 10:00:00 我: 你好\n"
        "2024-01-01 10:01:00 对方: 你好呀\n"
        "[2024-01-01 10:02:00] 我: 在干嘛\n"
        "2024-01-01 10:03:00 对方: 刚下班\n"
    )
    msgs = parse_import.parse_txt(text, "我", "对方")
    assert len(msgs) == 4, f"期望 4 条，实际 {len(msgs)}"
    assert msgs[0]["sender"] == "我"
    assert msgs[0]["content"] == "你好"
    assert msgs[1]["sender"] == "对方"
    assert msgs[1]["content"] == "你好呀"
    assert msgs[2]["content"] == "在干嘛"  # [time] 格式
    print("✅ parse_txt 通过")


def test_parse_csv_json():
    import csv as csv_mod
    import tempfile

    tmp = tempfile.mkdtemp()
    # CSV
    csv_path = os.path.join(tmp, "t.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv_mod.writer(f)
        w.writerow(["time", "sender", "content"])
        w.writerow(["2024-01-01 10:00:00", "我", "早上好"])
        w.writerow(["2024-01-01 10:05:00", "对方", "早"])
    msgs = parse_import.parse_csv(csv_path)
    assert len(msgs) == 2 and msgs[0]["content"] == "早上好"
    # JSON
    json_path = os.path.join(tmp, "t.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"messages": [
            {"timestamp": 1704067200, "sender": "我", "message_type": "text", "content": "hi"},
            {"timestamp": 1704067260, "sender": "对方", "message_type": "text", "content": "hello"},
        ]}, f)
    msgs = parse_import.parse_json(json_path)
    assert len(msgs) == 2 and msgs[1]["content"] == "hello"
    print("✅ parse_csv/parse_json 通过")


def _m(ts, sender, mtype="text", content="x", src="f", ref="r"):
    import datetime
    return {
        "timestamp": ts, "datetime": datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"),
        "sender": sender, "receiver": "other", "message_type": mtype, "content": content,
        "source_file": src, "source_reference": ref,
    }


def test_statistics():
    msgs = [
        _m(1704067200, "A", "text", "你好"),
        _m(1704067260, "B", "text", "你好"),
        _m(1704067320, "A", "text", "在吗"),
        _m(1704067380, "B", "text", "在"),
        _m(1704067380 + 25 * 3600, "A", "text", "隔了一天多"),
    ]
    s = statistics.compute(msgs)
    assert s["message_count"] == 5
    assert s["messages_by_sender"] == {"A": 3, "B": 2}
    assert len(s["breaks"]) >= 1  # 中间隔了一天
    assert "topic_initiations" in s
    print("✅ statistics 通过")


def test_merge_dedup():
    old = [_m(100, "A", "text", "a", "db", "r1"), _m(200, "B", "text", "b", "db", "r2")]
    new = [_m(100, "A", "text", "a", "db", "r1"), _m(300, "B", "text", "c", "db", "r3")]
    merged, added = merge_history.merge(new, old)
    assert len(merged) == 3, f"期望 3 条（去重后），实际 {len(merged)}"
    assert len(added) == 1 and added[0]["source_reference"] == "r3"
    print("✅ merge/dedup 通过")


if __name__ == "__main__":
    test_parse_txt()
    test_parse_csv_json()
    test_statistics()
    test_merge_dedup()
    print("\n🎉 全部测试通过")

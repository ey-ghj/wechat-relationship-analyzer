#!/usr/bin/env python3
"""测试记忆系统与数据安全脚本（profile/events/style/backup/safe_log）。

运行: python3 tests/test_memory.py
"""
import datetime
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import backup  # noqa: E402
import events  # noqa: E402
import profile  # noqa: E402
import safe_log  # noqa: E402
import style  # noqa: E402


def _m(ts, sender, content="x", mtype="text"):
    return {
        "timestamp": ts,
        "datetime": datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"),
        "sender": sender, "sender_name": sender,
        "receiver": "other", "receiver_name": "other",
        "message_type": mtype, "content": content,
        "source_file": "f", "source_reference": f"r{ts}",
    }


def test_profile():
    cfg = {"self_username": "me", "self_display_name": "我",
           "target_username": "other", "target_display_name": "对方"}
    p = profile.do_init(cfg, {"message_count": 10})
    assert p["self"]["username"] == "me"
    analysis = {
        "stage": {"name": "熟悉阶段", "confidence": "中", "basis": "聊日常"},
        "new_events": [{"type": "首次邀约", "datetime": "2026-11-01 10:00", "evidence": "一起吃饭", "outcome": "接受"}],
        "new_actions": [{"date": "2026-11-16", "action": "分享照片", "result": "回应", "note": ""}],
        "style": {"tone_notes": "轻松"},
    }
    p2 = profile.do_update(p, analysis, {"message_count": 12})
    assert p2["relationship"]["current_stage"] == "熟悉阶段"
    assert len(p2["key_events"]) == 1
    assert len(p2["actions_log"]) == 1
    assert p2["chat_style"]["tone_notes"] == "轻松"
    # 再次 update 相同事件应去重
    p3 = profile.do_update(p2, analysis, None)
    assert len(p3["key_events"]) == 1
    print("✅ profile 通过")


def test_events():
    msgs = [
        _m(100, "A", "你好"), _m(200, "B", "在吗"), _m(300, "A", "想约你"),
        _m(400, "B", "好啊"), _m(500, "A", "那明天见"),
    ]
    before, after = events.review(msgs, 300, 2, 2)
    assert len(before) == 2 and before[-1]["content"] == "想约你"
    assert len(after) == 2 and after[0]["content"] == "好啊"
    print("✅ events 通过")


def test_style():
    msgs = [
        _m(100, "A", "哈哈哈 好的", "text"),
        _m(200, "A", "嗯嗯", "text"),
        _m(300, "B", "好", "text"),
        _m(400, "A", "x", "emoji"),
    ]
    s = style.analyze(msgs)
    assert "A" in s and "B" in s
    assert s["A"]["emoji_ratio"] > 0
    assert s["A"]["avg_text_length"] > 0
    print("✅ style 通过")


def test_backup():
    tmp = tempfile.mkdtemp()
    data_dir = os.path.join(tmp, "data")
    os.makedirs(data_dir)
    with open(os.path.join(data_dir, "profile.json"), "w") as f:
        f.write("{}")
    bdir = os.path.join(tmp, "backups")
    dest = backup.backup(data_dir, bdir)
    assert os.path.exists(os.path.join(dest, "profile.json"))
    assert len(backup.list_backups(bdir)) == 1
    # 恢复
    os.remove(os.path.join(data_dir, "profile.json"))
    backup.restore(dest, data_dir)
    assert os.path.exists(os.path.join(data_dir, "profile.json"))
    shutil.rmtree(tmp)
    print("✅ backup 通过")


def test_safe_log():
    out = safe_log.desensitize("电话 13812345678 微信 wxid_abc123def")
    assert "13812345678" not in out
    assert "wxid_abc123def" not in out
    print("✅ safe_log 通过")


if __name__ == "__main__":
    test_profile()
    test_events()
    test_style()
    test_backup()
    test_safe_log()
    print("\n🎉 记忆系统测试全部通过")

#!/usr/bin/env python3
"""从已解密的微信数据库提取结构化聊天记录（统一 JSON 格式）。

复用 wcdb-key-tool/export_chat.py 里的解析逻辑（zstd 解压、引用/链接 XML 解析、
发送人映射），不重复造轮子。输出每条消息包含：

    timestamp, sender, receiver, message_type, content, source_file, source_reference

用法:
    python3 extract_structured.py --config config.json
    python3 extract_structured.py --config config.json --output data/messages.json
    python3 extract_structured.py --wcdb-dir /path/to/wcdb-key-tool \
        --self wxid_AAA --username wxid_BBB
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sqlite3
import sys


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_wcdb_dir(args, cfg) -> str:
    d = args.wcdb_dir or cfg.get("wcdb_tool_dir")
    if not d or not os.path.isdir(d):
        sys.exit(f"未找到 wcdb-key-tool 目录: {d}（请用 --wcdb-dir 或 config.json 指定）")
    return d


def import_export_chat(wcdb_dir: str):
    """复用 wcdb-key-tool/export_chat.py 的解析函数（唯一来源，不在本技能内另存副本）。"""
    if not wcdb_dir or not os.path.exists(os.path.join(wcdb_dir, "export_chat.py")):
        sys.exit(f"在 {wcdb_dir} 找不到 export_chat.py（请用 --wcdb-dir 指向 wcdb-key-tool）")
    if wcdb_dir not in sys.path:
        sys.path.insert(0, wcdb_dir)
    try:
        import export_chat as ec  # noqa: F401
    except ImportError as e:
        sys.exit(f"导入 export_chat 失败：{e}（缺依赖时先 pip install -r {wcdb_dir}/requirements.txt）")
    return ec


MESSAGE_DB_NAMES = ["message_0.db", "message_1.db", "message_2.db"]


def normalize_type(ec, local_type: int, content) -> str:
    """把微信 local_type 归一化成可读的消息类型。"""
    bt = ec.base_type(local_type)
    if bt == 1:
        return "text"
    if bt == 3:
        return "image"
    if bt == 34:
        return "voice"
    if bt == 43:
        return "video"
    if bt == 47:
        return "emoji"
    if bt == 48:
        return "location"
    if bt == 50:
        return "call"
    if bt == 10000:
        return "system"
    if bt == 49:
        # 引用回复 vs 链接/卡片/文件/小程序
        if isinstance(content, (bytes, bytearray)):
            try:
                s = content.decode("utf-8", errors="ignore")
            except Exception:
                s = ""
        else:
            s = str(content or "")
        if "<refermsg>" in s:
            return "reference"
        return "link"
    return f"type_{local_type}"


def extract(wcdb_dir: str, decrypted_subdir: str, self_username: str,
            target_username: str) -> list[dict]:
    ec = import_export_chat(wcdb_dir)
    decrypted = os.path.join(wcdb_dir, decrypted_subdir)
    contact_db = os.path.join(decrypted, "contact", "contact.db")

    # 显示名映射（备注优先，其次昵称）
    names = {}
    if os.path.exists(contact_db):
        conn = sqlite3.connect(contact_db)
        try:
            for u, remark, nick in conn.execute("SELECT username, remark, nick_name FROM contact"):
                names[u] = remark or nick or u
        except Exception:
            pass
        conn.close()

    def disp(u: str) -> str:
        if u == self_username:
            return "我"
        return names.get(u, u)

    tbl = "Msg_" + hashlib.md5(target_username.encode()).hexdigest()
    messages: list[dict] = []

    for db_name in MESSAGE_DB_NAMES:
        db_path = os.path.join(decrypted, "message", db_name)
        if not os.path.exists(db_path):
            continue
        conn = sqlite3.connect(db_path)
        has_tbl = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
        ).fetchone()
        if not has_tbl:
            conn.close()
            continue

        # sender id -> username (Name2Id 表 rowid 即 sender id)
        sender_names: dict[int, str] = {}
        try:
            for rowid, u in conn.execute("SELECT rowid, user_name FROM Name2Id"):
                sender_names[rowid] = u
        except Exception:
            pass

        for lid, create_time, local_type, sender_id, content, compress, ct in conn.execute(
            f'SELECT local_id, create_time, local_type, real_sender_id, '
            f'message_content, compress_content, WCDB_CT_message_content '
            f'FROM "{tbl}" ORDER BY create_time, local_id'
        ):
            c = content
            if (c is None or (isinstance(c, str) and not c)) and compress is not None:
                c = compress
            # zstd 解压
            if ct == 4 and isinstance(c, (bytes, bytearray)):
                try:
                    c = ec._ZSTD.decompress(c)
                except Exception:
                    pass

            sender_username = sender_names.get(sender_id, f"unknown_{sender_id}")
            receiver_username = self_username if sender_username != self_username else target_username
            mtype = normalize_type(ec, local_type, c)
            # 可读内容
            body = ec.fmt_content(local_type, c)

            messages.append({
                "timestamp": int(create_time),
                "datetime": datetime.datetime.fromtimestamp(create_time).strftime("%Y-%m-%d %H:%M:%S"),
                "sender": sender_username,
                "sender_name": disp(sender_username),
                "receiver": receiver_username,
                "receiver_name": disp(receiver_username),
                "message_type": mtype,
                "content": body,
                "source_file": db_name,
                "source_reference": f"{tbl}:local_id={lid}",
            })
        conn.close()

    messages.sort(key=lambda m: (m["timestamp"], m["source_file"]))
    return messages


def main():
    ap = argparse.ArgumentParser(description="提取结构化微信聊天记录")
    ap.add_argument("--config", default="config.json", help="配置文件路径")
    ap.add_argument("--wcdb-dir", help="wcdb-key-tool 目录（覆盖 config）")
    ap.add_argument("--self", help="自己的 username（覆盖 config）")
    ap.add_argument("--username", help="目标联系人 username（覆盖 config）")
    ap.add_argument("--output", help="输出 JSON 路径")
    args = ap.parse_args()

    cfg = load_config(args.config) if os.path.exists(args.config) else {}
    wcdb_dir = resolve_wcdb_dir(args, cfg)
    self_username = args.self or cfg.get("self_username")
    target_username = args.username or cfg.get("target_username")
    if not self_username or not target_username:
        sys.exit("请提供 self_username 和 target_username（--self/--username 或 config.json）")

    msgs = extract(wcdb_dir, cfg.get("decrypted_subdir", "decrypted"),
                   self_username, target_username)

    out = args.output or os.path.join("data", "messages.json")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    payload = {
        "self_username": self_username,
        "target_username": target_username,
        "extracted_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message_count": len(msgs),
        "messages": msgs,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"✅ 提取 {len(msgs)} 条消息 -> {out}")


if __name__ == "__main__":
    main()

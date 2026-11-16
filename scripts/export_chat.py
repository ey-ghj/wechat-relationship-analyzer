#!/usr/bin/env python3
"""导出某个联系人的完整聊天记录为 Markdown。

用法:
    python3 export_chat.py --name "蒋昌宇"              # 按显示名/备注/昵称/微信号搜索
    python3 export_chat.py --username wxid_xxx           # 直接按 username 导出
    python3 export_chat.py --username xxx@chatroom       # 群聊
    python3 export_chat.py --name "蒋" --list            # 只列出候选，不导出

输出: exports/<显示名>.md
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import html
import os
import re
import sqlite3

import zstandard

_ZSTD = zstandard.ZstdDecompressor()

BASE = os.path.dirname(os.path.abspath(__file__))
DECRYPTED = os.path.join(BASE, "decrypted")
CONTACT_DB = os.path.join(DECRYPTED, "contact", "contact.db")
SESSION_DB = os.path.join(DECRYPTED, "session", "session.db")
MESSAGE_DBS = [
    os.path.join(DECRYPTED, "message", "message_0.db"),
    os.path.join(DECRYPTED, "message", "message_1.db"),
    os.path.join(DECRYPTED, "message", "message_2.db"),
]
# 当前登录账号（本机账号 wxid_quojkfn0e29122）
SELF = "wxid_quojkfn0e29122"


def base_type(t: int) -> int:
    """微信 4.x 把子类型编码在高 32 位，取低 32 位得到基础类型。"""
    return t & 0xFFFFFFFF if t > 0xFFFFFFFF else t


def extract_readable(blob):
    """尽力从二进制/文本里提取可读的中英文片段（用于系统消息等）。"""
    if blob is None:
        return ""
    if isinstance(blob, str):
        return blob.strip()
    try:
        s = blob.decode("utf-8", errors="ignore")
    except Exception:
        return ""
    parts = re.findall(r"[\u4e00-\u9fffA-Za-z0-9，。！？、：；（）【】《》“”‘’@/\.\-_ ]{2,}", s)
    return " ".join(p for p in parts if p.strip())


def extract_chinese(blob):
    """从二进制里只提取中文为主的连续片段（用于引用/卡片，避免 ASCII 噪声）。"""
    if blob is None:
        return ""
    if isinstance(blob, str):
        return blob.strip()
    try:
        s = blob.decode("utf-8", errors="ignore")
    except Exception:
        return ""
    # 以中文开头、中文占比高的片段
    parts = re.findall(r"[\u4e00-\u9fff][\u4e00-\u9fff，。！？、：；（）【】《》0-9a-zA-Z@/\.\-_% ]*", s)
    good = []
    for p in parts:
        cjk = sum(1 for c in p if "\u4e00" <= c <= "\u9fff")
        if cjk >= 3 and cjk >= len(p) * 0.5:  # 至少 3 个汉字且中文占一半以上
            good.append(p)
    return " ".join(good).strip()


def _summarize_quoted(s: str) -> str:
    """把「被引用内容」整理成简短可读文本（可能是纯文本，也可能是嵌套 XML）。"""
    s = (s or "").strip()
    if not s:
        return ""
    if not s.startswith("<"):
        return s  # 纯文本
    # 嵌套 XML（被引用的是图片/视频/引用/链接等）
    if "<img" in s:
        return "[图片]"
    if "<video" in s:
        return "[视频]"
    if "<emoji" in s:
        return "[表情]"
    if "<voicemsg" in s:
        return "[语音]"
    title = (re.search(r"<title>(.*?)</title>", s, re.DOTALL) or [None, ""])[1]
    if (title or "").strip():
        return (title or "").strip()
    des = (re.search(r"<des>(.*?)</des>", s, re.DOTALL) or [None, ""])[1]
    if (des or "").strip():
        return (des or "").strip()
    return "[卡片]"


def parse_app_msg(content) -> str:
    """解析 type=49 的 app 消息（已解压的 XML，可能是 bytes 或 str）。

    引用回复(type 57)结构:
        <title>回复文本</title>
        <refermsg><displayname>昵称</displayname><content>引用原文</content></refermsg>
    链接等:
        <title>标题</title><des>摘要</des>
    """
    if content is None:
        return "[卡片/链接]"
    if isinstance(content, (bytes, bytearray)):
        s = content.decode("utf-8", errors="ignore")
    else:
        s = str(content)
    s = html.unescape(s)

    title = (re.search(r"<title>(.*?)</title>", s, re.DOTALL) or [None, ""])[1]
    title = (title or "").strip()
    quoted = (re.search(r"<refermsg>.*?<content>(.*?)</content>", s, re.DOTALL) or [None, ""])[1]
    quoted = (quoted or "").strip()
    name = (re.search(r"<refermsg>.*?<displayname>(.*?)</displayname>", s, re.DOTALL) or [None, ""])[1]
    name = (name or "").strip()
    des = (re.search(r"<des>(.*?)</des>", s, re.DOTALL) or [None, ""])[1]
    des = (des or "").strip()

    if "<refermsg>" in s:  # 引用回复
        parts = []
        if title:
            parts.append(f"回复「{title}」")
        q = _summarize_quoted(quoted)
        if q:
            who = f"{name}：" if name else ""
            parts.append(f"引用 {who}{q}")
        return " ↩ ".join(parts) if parts else "[引用]"

    # 链接 / 文件 / 名片 / 小程序等
    if title:
        return title + (f" — {des}" if des else "")
    if des:
        return des
    return "[卡片/链接]"


def parse_system_msg(content) -> str:
    """解析系统消息（可能是纯文本，也可能是 XML，如撤回消息）。"""
    if content is None:
        return ""
    if isinstance(content, (bytes, bytearray)):
        try:
            content = content.decode("utf-8", errors="ignore")
        except Exception:
            return ""
    content = str(content)
    if "<" in content and ">" in content:  # XML 结构
        content = html.unescape(content)
        for tag in ("replacemsg", "content", "title"):
            m = re.search(rf"<{tag}>(.*?)</{tag}>", content, re.DOTALL)
            if m and m.group(1).strip():
                return m.group(1).strip()
        return ""  # XML 但无标准字段，不给垃圾文本
    return content.strip()


def fmt_content(local_type: int, content) -> str:
    bt = base_type(local_type)
    if bt == 1:  # 文本
        return content if isinstance(content, str) and content else ""
    if bt == 3:
        return "[图片]"
    if bt == 43:
        return "[视频]"
    if bt == 34:
        return "[语音]"
    if bt == 47:
        return "[表情]"
    if bt == 48:
        return "[位置]"
    if bt == 50:
        return "[语音通话]"
    if bt == 10000:
        txt = parse_system_msg(content)
        return "[系统消息]" + ((" " + txt) if txt else "")
    if bt == 49:  # 链接/文件/名片/引用回复等（XML，可能已解压）
        return parse_app_msg(content)
    return f"[类型{local_type}]"


def load_contacts() -> dict[str, str]:
    """username -> 显示名（备注优先，其次昵称）。"""
    out: dict[str, str] = {}
    if not os.path.exists(CONTACT_DB):
        return out
    conn = sqlite3.connect(CONTACT_DB)
    try:
        for username, remark, nick in conn.execute(
            "SELECT username, remark, nick_name FROM contact"
        ):
            out[username] = remark or nick or username
    except Exception:
        pass
    conn.close()
    return out


def search_contacts(q: str) -> list[tuple[str, str]]:
    conn = sqlite3.connect(CONTACT_DB)
    like = f"%{q}%"
    rows = conn.execute(
        "SELECT username, remark, nick_name, alias FROM contact "
        "WHERE username LIKE ? OR remark LIKE ? OR nick_name LIKE ? OR alias LIKE ?",
        (like, like, like, like),
    ).fetchall()
    conn.close()
    return [(u, r or n or a or u) for u, r, n, a in rows]


def resolve_display(contacts: dict[str, str], username: str) -> str:
    if username == SELF:
        return "我"
    if username in contacts:
        return contacts[username]
    return username


def collect_messages(username: str) -> tuple[list, str]:
    """在三个 message DB 里收集该 username 的所有消息，返回 (消息列表, 表名)。"""
    h = hashlib.md5(username.encode()).hexdigest()
    tbl = "Msg_" + h
    msgs = []
    found_db = None
    for db in MESSAGE_DBS:
        if not os.path.exists(db):
            continue
        conn = sqlite3.connect(db)
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
        ).fetchall()]
        if names:
            found_db = db
            for lid, create_time, local_type, sender, content, compress, ct in conn.execute(
                f'SELECT local_id, create_time, local_type, real_sender_id, '
                f'message_content, compress_content, WCDB_CT_message_content FROM "{tbl}" ORDER BY create_time, local_id'
            ):
                # 文本可能在 message_content 或 compress_content
                c = content
                if (c is None or (isinstance(c, str) and not c)) and compress is not None:
                    c = compress
                # WCDB 内置压缩（WCDB_CT_message_content=4 表示 zstd）解压
                if ct == 4 and isinstance(c, (bytes, bytearray)):
                    try:
                        c = _ZSTD.decompress(c)
                    except Exception:
                        pass
                msgs.append((create_time, local_type, sender, c))
        conn.close()
    msgs.sort(key=lambda x: (x[0], x[1] if isinstance(x[1], int) else 0))
    return msgs, tbl


def sender_map(contacts: dict[str, str], dbs: list[str]) -> dict[int, str]:
    """real_sender_id -> 显示名。Name2Id 表 rowid 即 sender id。"""
    m: dict[int, str] = {}
    for db in dbs:
        if not os.path.exists(db):
            continue
        conn = sqlite3.connect(db)
        try:
            for rowid, username in conn.execute(
                "SELECT rowid, user_name FROM Name2Id"
            ):
                m[rowid] = resolve_display(contacts, username)
        except Exception:
            pass
        conn.close()
    return m


def export(username: str, out_path: str) -> None:
    contacts = load_contacts()
    display = resolve_display(contacts, username)
    msgs, tbl = collect_messages(username)
    if not msgs:
        print(f"未找到 {username} 的任何消息")
        return

    senders = sender_map(contacts, MESSAGE_DBS)

    tmin = datetime.datetime.fromtimestamp(msgs[0][0])
    tmax = datetime.datetime.fromtimestamp(msgs[-1][0])

    lines = []
    lines.append(f"# 与「{display}」的聊天记录")
    lines.append("")
    lines.append(f"- 微信账号 username: `{username}`")
    lines.append(f"- 消息总数: {len(msgs)} 条")
    lines.append(f"- 时间范围: {tmin:%Y-%m-%d %H:%M} ~ {tmax:%Y-%m-%d %H:%M}")
    lines.append(f"- 导出时间: {datetime.datetime.now():%Y-%m-%d %H:%M}")
    lines.append("")

    cur_day = None
    for create_time, local_type, sender, content in msgs:
        dt = datetime.datetime.fromtimestamp(create_time)
        day = dt.strftime("%Y-%m-%d")
        if day != cur_day:
            cur_day = day
            lines.append("")
            lines.append(f"## {day}")
            lines.append("")
        who = senders.get(sender, f"未知({sender})")
        body = fmt_content(local_type, content)
        body = body.replace("\n", " ").strip()
        if body:
            lines.append(f"- **{dt:%H:%M}** {who}：{body}")
        else:
            lines.append(f"- **{dt:%H:%M}** {who}：[空消息]")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"✅ 已导出 {len(msgs)} 条消息 -> {out_path}")


def main():
    ap = argparse.ArgumentParser(description="导出微信聊天记录为 Markdown")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--username", help="直接指定 username（wxid_xxx 或 xxx@chatroom）")
    g.add_argument("--name", help="按显示名/备注/昵称/微信号搜索")
    ap.add_argument("--list", action="store_true", help="只列出候选，不导出")
    ap.add_argument("--output", help="输出文件路径")
    ap.add_argument("--decrypted", default="decrypted",
                    help="解密目录名（默认 decrypted，可指定 decrypted_k93y8k52gomi22 等）")
    args = ap.parse_args()

    # 让脚本作用于指定账号的解密目录
    global DECRYPTED, CONTACT_DB, SESSION_DB, MESSAGE_DBS
    DECRYPTED = args.decrypted if os.path.isabs(args.decrypted) else os.path.join(BASE, args.decrypted)
    CONTACT_DB = os.path.join(DECRYPTED, "contact", "contact.db")
    SESSION_DB = os.path.join(DECRYPTED, "session", "session.db")
    MESSAGE_DBS = [os.path.join(DECRYPTED, "message", f"message_{i}.db") for i in range(3)]

    if args.username:
        candidates = [(args.username, args.username)]
    else:
        candidates = search_contacts(args.name)
        if not candidates:
            print(f"未找到匹配「{args.name}」的联系人")
            return

    if args.list:
        print(f"匹配「{args.name}」的候选：")
        for u, disp in candidates:
            print(f"  {disp}  ({u})")
        return

    if len(candidates) > 1:
        print("匹配到多个，请用 --username 精确指定：")
        for u, disp in candidates:
            print(f"  {disp}  ({u})")
        return

    username, display = candidates[0]
    out = args.output or os.path.join(BASE, "exports", f"{display}.md")
    export(username, out)


if __name__ == "__main__":
    main()

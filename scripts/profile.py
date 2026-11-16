#!/usr/bin/env python3
"""关系档案管理 —— 长期恋爱关系记忆的核心。

维护 data/profile.json，持久化：
- 双方档案（self / target）
- 关系阶段 + 阶段变化历史
- 重要事件时间线（key_events）
- 用户行动与结果记录（actions_log）
- 个人聊天风格档案（chat_style）
- 统计快照（stats_snapshots，供进度对比）

用法:
    python3 profile.py init --config config.json [--stats data/stats.json]
    python3 profile.py update --input analysis.json [--stats data/stats.json]
    python3 profile.py view [--json]
    python3 profile.py archive
    python3 profile.py history
"""
from __future__ import annotations

import argparse
import copy
import datetime
import json
import os
import sys

DEFAULT_PROFILE = os.path.join("data", "profile.json")
HISTORY_DIR = os.path.join("data", "history")
SCHEMA_VERSION = 1


def now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def new_profile(config: dict) -> dict:
    return {
        "version": SCHEMA_VERSION,
        "created_at": now_str(),
        "updated_at": now_str(),
        "self": {
            "username": config.get("self_username", ""),
            "display_name": config.get("self_display_name", "我"),
        },
        "target": {
            "username": config.get("target_username", ""),
            "display_name": config.get("target_display_name", "对方"),
        },
        "relationship": {
            "current_stage": None,
            "stage_confidence": None,
            "stage_history": [],
        },
        "key_events": [],
        "actions_log": [],
        "chat_style": {},
        "stats_snapshots": [],
    }


def _event_key(e: dict) -> str:
    return f"{e.get('type', '')}|{e.get('datetime', '')}"


def _merge_events(existing: list, new: list) -> list:
    out = list(existing)
    seen = {_event_key(e) for e in out}
    for e in new:
        if _event_key(e) not in seen:
            out.append(e)
            seen.add(_event_key(e))
    out.sort(key=lambda e: e.get("datetime", ""))
    return out


def do_init(config: dict, stats: dict | None) -> dict:
    profile = new_profile(config)
    if stats:
        profile["stats_snapshots"].append({
            "date": now_str(),
            "message_count": stats.get("message_count"),
            "time_range": stats.get("time_range"),
            "stage": None,
        })
    return profile


def do_update(profile: dict, analysis: dict, stats: dict | None) -> dict:
    profile = copy.deepcopy(profile)
    profile["version"] = SCHEMA_VERSION
    profile["updated_at"] = now_str()

    # 关系阶段
    stage = analysis.get("stage") or {}
    if stage.get("name"):
        rel = profile.setdefault("relationship", {})
        prev = rel.get("current_stage")
        rel["current_stage"] = stage["name"]
        rel["stage_confidence"] = stage.get("confidence")
        rel.setdefault("stage_history", []).append({
            "date": now_str(),
            "from": prev,
            "to": stage["name"],
            "confidence": stage.get("confidence"),
            "basis": stage.get("basis", ""),
        })

    # 关键事件
    new_events = analysis.get("new_events") or []
    if new_events:
        profile["key_events"] = _merge_events(profile.get("key_events", []), new_events)

    # 行动记录
    new_actions = analysis.get("new_actions") or []
    if new_actions:
        profile.setdefault("actions_log", []).extend(new_actions)

    # 聊天风格
    style = analysis.get("style") or {}
    if style:
        profile.setdefault("chat_style", {}).update(style)

    # 统计快照
    if stats:
        profile.setdefault("stats_snapshots", []).append({
            "date": now_str(),
            "message_count": stats.get("message_count"),
            "time_range": stats.get("time_range"),
            "stage": stage.get("name"),
        })

    return profile


def _load_config(args) -> dict:
    if os.path.exists(args.config):
        with open(args.config, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _read_stats(path: str | None) -> dict | None:
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(description="关系档案管理")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="初始化档案")
    p_init.add_argument("--config", default="config.json")
    p_init.add_argument("--stats")
    p_init.add_argument("--profile", default=DEFAULT_PROFILE)

    p_upd = sub.add_parser("update", help="合并分析结果到档案")
    p_upd.add_argument("--input", required=True, help="分析结果 JSON（含 stage/new_events/new_actions/style）")
    p_upd.add_argument("--stats", help="当前统计 JSON（记录快照）")
    p_upd.add_argument("--profile", default=DEFAULT_PROFILE)

    p_view = sub.add_parser("view", help="查看档案")
    p_view.add_argument("--json", action="store_true")
    p_view.add_argument("--profile", default=DEFAULT_PROFILE)

    p_arc = sub.add_parser("archive", help="归档当前档案到 history/")
    p_arc.add_argument("--profile", default=DEFAULT_PROFILE)

    p_hist = sub.add_parser("history", help="列出历史归档")
    p_hist.add_argument("--dir", default=HISTORY_DIR)

    args = ap.parse_args()

    if args.cmd == "init":
        cfg = _load_config(args)
        profile = do_init(cfg, _read_stats(args.stats))
        save(args.profile, profile)
        print(f"✅ 档案已初始化 -> {args.profile}")

    elif args.cmd == "update":
        if not os.path.exists(args.profile):
            sys.exit(f"档案不存在: {args.profile}（先运行 init）")
        analysis = load(args.input)
        if not analysis:
            sys.exit(f"分析结果为空: {args.input}")
        profile = do_update(load(args.profile), analysis, _read_stats(args.stats))
        save(args.profile, profile)
        n_evt = len(profile["key_events"])
        n_act = len(profile["actions_log"])
        stage = profile["relationship"]["current_stage"] or "未判定"
        print(f"✅ 档案已更新 -> {args.profile}")
        print(f"   阶段: {stage} | 事件 {n_evt} 条 | 行动 {n_act} 条")

    elif args.cmd == "view":
        profile = load(args.profile)
        if not profile:
            sys.exit(f"档案不存在: {args.profile}")
        if args.json:
            print(json.dumps(profile, ensure_ascii=False, indent=2))
        else:
            print(f"双方: {profile['self']['display_name']} ↔ {profile['target']['display_name']}")
            rel = profile.get("relationship", {})
            print(f"当前阶段: {rel.get('current_stage') or '未判定'} (可信度: {rel.get('stage_confidence') or '-'})")
            print(f"阶段历史: {len(rel.get('stage_history', []))} 条")
            print(f"关键事件: {len(profile.get('key_events', []))} 条")
            print(f"行动记录: {len(profile.get('actions_log', []))} 条")
            print(f"统计快照: {len(profile.get('stats_snapshots', []))} 次")
            print(f"最近更新: {profile.get('updated_at')}")

    elif args.cmd == "archive":
        if not os.path.exists(args.profile):
            sys.exit(f"档案不存在: {args.profile}")
        profile = load(args.profile)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(HISTORY_DIR, exist_ok=True)
        dest = os.path.join(HISTORY_DIR, f"profile_{stamp}.json")
        save(dest, profile)
        print(f"✅ 已归档 -> {dest}")

    elif args.cmd == "history":
        if not os.path.isdir(args.dir):
            print("（暂无历史归档）")
            return
        files = sorted(f for f in os.listdir(args.dir) if f.startswith("profile_"))
        for f in files:
            print(" ", f)


if __name__ == "__main__":
    main()

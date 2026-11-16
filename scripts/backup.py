#!/usr/bin/env python3
"""数据备份与异常恢复。

备份 data/ 下的档案与历史（messages.json/stats.json/profile.json/history/），
支持恢复到指定备份点。用于防止误操作或异常导致记忆丢失。

用法:
    python3 backup.py backup --data-dir data --backup-dir backups
    python3 backup.py list --backup-dir backups
    python3 backup.py restore --backup backups/backup_20261116_220000 --data-dir data
"""
from __future__ import annotations

import argparse
import datetime
import os
import shutil


def backup(data_dir: str, backup_dir: str) -> str:
    if not os.path.isdir(data_dir):
        print(f"[WARN] 数据目录不存在: {data_dir}")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(backup_dir, f"backup_{stamp}")
    os.makedirs(backup_dir, exist_ok=True)
    if os.path.isdir(data_dir):
        shutil.copytree(data_dir, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    else:
        os.makedirs(dest)
    # 记录备份元信息
    with open(os.path.join(dest, "_backup_meta.txt"), "w") as f:
        f.write(f"created_at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"source: {data_dir}\n")
    return dest


def list_backups(backup_dir: str) -> list[str]:
    if not os.path.isdir(backup_dir):
        return []
    return sorted(d for d in os.listdir(backup_dir) if d.startswith("backup_"))


def restore(backup_path: str, data_dir: str) -> None:
    if not os.path.isdir(backup_path):
        raise SystemExit(f"备份不存在: {backup_path}")
    # 恢复前先把当前 data/ 再备份一次，避免覆盖丢失
    if os.path.isdir(data_dir):
        pre = os.path.join(os.path.dirname(backup_path.rstrip("/")), "pre_restore_"
                           + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        shutil.copytree(data_dir, pre, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        print(f"[*] 恢复前已备份当前数据到 {pre}")
        shutil.rmtree(data_dir)
    shutil.copytree(backup_path, data_dir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # 清理元信息文件
    meta = os.path.join(data_dir, "_backup_meta.txt")
    if os.path.exists(meta):
        os.unlink(meta)
    print(f"✅ 已恢复到 {data_dir}")


def main():
    ap = argparse.ArgumentParser(description="数据备份与恢复")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_b = sub.add_parser("backup", help="备份 data/")
    p_b.add_argument("--data-dir", default="data")
    p_b.add_argument("--backup-dir", default="backups")

    p_l = sub.add_parser("list", help="列出备份")
    p_l.add_argument("--backup-dir", default="backups")

    p_r = sub.add_parser("restore", help="恢复到备份点")
    p_r.add_argument("--backup", required=True)
    p_r.add_argument("--data-dir", default="data")

    args = ap.parse_args()

    if args.cmd == "backup":
        dest = backup(args.data_dir, args.backup_dir)
        print(f"✅ 备份完成 -> {dest}")
    elif args.cmd == "list":
        for d in list_backups(args.backup_dir):
            print(" ", d)
    elif args.cmd == "restore":
        restore(args.backup, args.data_dir)


if __name__ == "__main__":
    main()

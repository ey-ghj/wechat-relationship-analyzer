#!/usr/bin/env python3
"""日志脱敏工具。

对输出中可能出现的手机号、微信号做掩码，避免日志泄露个人敏感信息。
分析报告里的聊天原文属用户主动查看的内容，不在此脱敏范围内；
本模块用于脚本自身的日志/提示输出。
"""
from __future__ import annotations

import re

_PHONE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
_WXID = re.compile(r"(wxid_[a-z0-9]{4,})")


def desensitize(text: str) -> str:
    """掩码 11 位手机号 和 wxid。"""
    if not text:
        return text
    text = _PHONE.sub(lambda m: m.group(1)[:3] + "****" + m.group(1)[-4:], text)
    text = _WXID.sub(lambda m: m.group(1)[:8] + "…", text)
    return text


if __name__ == "__main__":
    print(desensitize("电话 13812345678 微信 wxid_abc123def456"))

---
name: wechat-relationship-analyzer
description: 分析微信聊天记录，还原互动时间线，识别双方关系所处阶段（初识/暧昧/升温/稳定/降温等），提取关键事件并复盘，长期追踪恋爱进度（关系档案+事件时间线+互动历史+个人聊天风格），基于完整历史上下文生成自然回复建议。当用户导入微信聊天记录或截图、想了解「我和 TA 什么关系」「关系有没有进展」「该怎么回 TA」时使用。
---

# 微信聊天记录提取与恋爱进度分析

从微信聊天记录中提取结构化数据，分析双方关系状态与变化，并**长期记忆关系背景、持续追踪进展、复盘关键事件、提供个性化聊天建议**。
**只处理用户主动提供或有权访问的数据**，全程本地，不上传任何内容。

## 何时使用

- 导入/分析微信（或 QQ）聊天记录、截图、语音转写
- 「我和 TA 现在算什么阶段」「TA 对我有没有意思」
- 「最近 TA 变冷淡了」「关系有没有进展」「回顾一下上次冲突」
- 「这句话该怎么回」「帮我回一下这条消息」

## 数据来源

1. **本机微信数据库（最完整）**：需预先用 [`wcdb-key-tool`](https://github.com/TANGandXUE/wcdb-key-tool) 解密，再用 `scripts/extract_structured.py` 提取。
2. **导出的聊天文件**：TXT / CSV / JSON / HTML，用 `scripts/parse_import.py`。
3. **聊天截图**：`scripts/parse_import.py` 会自动 OCR（macOS 用系统 Vision，其他平台用 Tesseract）。

## 记忆感知工作流（每次分析都执行）

### 第 0 步：数据安全

```bash
# 分析前先备份，原始记录只读（脚本从不修改源数据库/源文件）
python3 scripts/backup.py backup --data-dir data --backup-dir backups
```

### 第 1 步：提取结构化数据

```bash
python3 scripts/extract_structured.py --config config.json --output data/messages.json
# 或：python3 scripts/parse_import.py --input 记录.txt --input 截图.png --self 我 --target 对方
```

### 第 2 步：客观统计 + 风格

```bash
python3 scripts/statistics.py --input data/messages.json --output data/stats.json
python3 scripts/style.py --input data/messages.json --output data/style.json
```

`stats.json` 含**最近 7 天 / 30 天窗口对比**（`recent_windows`），用于进度追踪。

### 第 3 步：增量合并（有历史时）

```bash
python3 scripts/merge_history.py --input data/messages.json \
    --history data/history/messages.json \
    --output data/history/messages.json --progress data/progress.json
```

### 第 4 步：读取历史记忆（关键！）

```bash
python3 scripts/profile.py view   # 查看关系档案（阶段/事件/行动/风格/快照）
```

**必须先读 `data/profile.json`**（关系档案），结合历史完整上下文做分析，
不能每次从零开始、不能与历史结论自相矛盾。若档案不存在，先 `init`：

```bash
python3 scripts/profile.py init --config config.json --stats data/stats.json
```

### 第 5 步：分析（LLM 完成）

读取 `data/messages.json`（消息）、`data/stats.json`（统计，含 7/30 天）、
`data/style.json`（风格指标）、`data/profile.json`（历史记忆），
结合 `references/relationship_stages.md` 和 `references/analysis_rules.md` 产出报告。

### 第 6 步：关键事件复盘

对某个关键事件，用 `events.py` 提取事件前后上下文再分析：

```bash
python3 scripts/events.py list                              # 列出已记录的关键事件
python3 scripts/events.py review --datetime "2026-11-03 20:00" \
    --input data/messages.json --before 20 --after 20       # 提取前后文
```

复盘要点见 `references/event_review.md`：结合事件前因、双方反应、后续行动、关系变化。

### 第 7 步：更新记忆 + 归档

把本次分析结论写回档案，实现长期记忆：

```bash
# 1. 生成分析结果 JSON（stage/new_events/new_actions/style 字段）
python3 scripts/profile.py update --input analysis.json --stats data/stats.json
# 2. 归档当前档案（保留历史快照）
python3 scripts/profile.py archive
```

`analysis.json` 结构：
```json
{
  "stage": {"name": "关系阶段", "confidence": "高/中/低", "basis": "判断依据"},
  "new_events": [{"type": "首次邀约", "datetime": "...", "evidence": "...", "analysis": "...", "outcome": "..."}],
  "new_actions": [{"date": "...", "action": "做了什么", "result": "结果", "note": ""}],
  "style": {"tone_notes": "...", "common_phrases": [...]}
}
```

## 分析维度

1. **关系阶段**：初识→熟悉→互相了解→暧昧→升温→约会→确认→稳定→降温/停滞。
   证据不足标「不确定」，不强归类。
2. **双方互动**：谁更主动、是否延续话题、主动关心、情绪价值、分享生活、试探/暧昧、邀约、边界感。
3. **情绪与态度变化**：亲密程度、热情、冷淡信号、情绪波动、积极反馈、回避行为。
   **必须结合上下文，不凭单句话判断心理。**
4. **关键事件时间线**：第一次主动聊天/邀约/见面/表达好感/暧昧/冲突与道歉/转折点，各带时间+原文。
5. **进度对比**：用 `stats.json` 的 `recent_7d` / `recent_30d` 对比近期 vs 整体（频率、主动、深夜、非文本占比）。

## 个人聊天风格档案

`style.py` 产出客观风格指标（平均长度、表情占比、标点习惯、高频短语、时段分布）。
分析回复建议时，**必须参考 `data/profile.json` 的 `chat_style` 和 `data/style.json`**，
让回复贴合用户平时表达习惯，避免 AI 味、避免过度热情或刻意讨好。

## 报告输出

按 `references/report_template.md` 结构：A 当前关系状态 · B 最近聊天分析 · C 关键证据 · D 关系趋势 · E 下一步建议 · F 回复辅助。
每个重要结论带「证据：原文 + 时间」，并区分【事实】【推测】【不确定】。

## 硬性规则

- **原始记录只读**：脚本从不修改源数据库/源文件，分析副本与原始数据分离。
- **不凭单句话判断心理**，不把消息数量/回复速度等同于感情投入。
- **不强行制造进展**；无明显变化就说「当前无足够证据表明关系变化」。
- **不提供操控/PUA/欺骗类建议**；回复建议保留用户原风格、尊重边界。
- **日志脱敏**：脚本日志用 `scripts/safe_log.py` 的 `desensitize` 掩码手机号/微信号；聊天原文不进日志。
- **异常恢复**：分析前 `backup.py backup`，出错时 `backup.py restore`。
- **不泄露聊天原文**；密钥与本地配置不入库（已在 `.gitignore`）。

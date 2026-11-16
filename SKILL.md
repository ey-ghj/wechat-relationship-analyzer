---
name: wechat-relationship-analyzer
description: 分析微信聊天记录，还原互动时间线，识别双方关系所处阶段（初识/暧昧/升温/稳定/降温等），提取关键事件，追踪恋爱进度，并基于上下文生成自然的回复建议。当用户导入微信聊天记录、提供聊天截图或语音转写、希望 AI 分析「我和 TA 现在什么关系」「关系有没有进展」「该怎么回 TA」时使用。
---

# 微信聊天记录提取与恋爱进度分析

从微信聊天记录中提取结构化数据，分析双方关系状态与变化，并持续追踪进展。
**只处理用户主动提供或有权访问的数据**，全程本地，不上传任何内容。

## 何时使用

用户出现以下诉求时启用本技能：
- 导入/分析微信（或 QQ）聊天记录，想了解双方关系
- 「我和 TA 现在算什么阶段」「TA 对我有没有意思」
- 「最近 TA 变冷淡了」「关系有没有进展」
- 「这句话该怎么回」「帮我回一下这条消息」
- 提供聊天截图、语音转写文本需要分析

## 数据来源（二选一）

1. **本机微信数据库（推荐，最完整）**：需要预先用 `wcdb-key-tool` 解密。
   运行 `scripts/extract_structured.py` 从解密库提取。
2. **导出的聊天文件**：TXT / CSV / JSON / HTML / 截图 OCR 文本。
   运行 `scripts/parse_import.py` 导入。

## 工作流

### 第 1 步：提取结构化数据

```bash
# 从微信数据库提取（需 config.json 配置 wcdb_tool_dir / self_username / target_username）
python3 scripts/extract_structured.py --config config.json --output data/messages.json

# 或从导出文件导入（多文件用多个 --input）
python3 scripts/parse_import.py --input 聊天记录.txt --input 记录2.csv \
    --self 我 --target 对方 --output data/messages.json
```

### 第 2 步：计算客观统计

```bash
python3 scripts/statistics.py --input data/messages.json --output data/stats.json
```

### 第 3 步：增量合并（有历史时）

```bash
python3 scripts/merge_history.py --input data/messages.json \
    --history data/history/messages.json \
    --output data/history/messages.json --progress data/progress.json
```

### 第 4 步：分析（LLM 完成）

读取 `data/messages.json`（消息）和 `data/stats.json`（统计），结合
`references/relationship_stages.md`（阶段定义）和
`references/analysis_rules.md`（分析规则），产出报告。

若存在 `data/profile.json`（历史进度档案），先读它，做历史对比；
若存在 `data/progress.json`（本次增量），识别新增关键事件。

### 第 5 步：更新进度档案

把本次分析结论（阶段、关键事件、统计快照）写入 `data/profile.json`，
供下次增量对比，避免每次从零开始。

## 分析维度（详见 references）

1. **关系阶段识别**：初识→熟悉→互相了解→暧昧→升温→约会→确认→稳定→降温/停滞。
   证据不足时标「不确定」，不强归类。
2. **双方互动**：谁更主动、是否延续话题、主动关心、情绪价值、分享生活、试探/暧昧表达、邀约、边界感。
3. **情绪与态度变化**：亲密程度、热情、冷淡信号、情绪波动、积极反馈、回避行为。
   必须结合上下文，不单凭一句话判断心理。
4. **关键事件时间线**：第一次主动聊天/邀约/见面/表达好感/暧昧/冲突与道歉/转折点，各带时间+原文。

## 报告输出

按 `references/report_template.md` 的结构输出，包含：
A. 当前关系状态 · B. 最近聊天分析 · C. 关键证据 · D. 关系趋势 · E. 下一步建议 · F. 回复辅助。

每个重要结论必须带「证据：原文 + 时间」，并区分【事实】【推测】【不确定】。

## 硬性规则

- **不得删减或改动原始聊天记录**；分析副本与原始数据分离保存。
- **不根据单一消息下结论**，不把消息数量/回复速度等同于感情投入。
- **不强行制造进展**；无明显变化就明确说明「当前无足够证据表明关系变化」。
- **不提供操控/PUA/欺骗类建议**；回复建议保留用户原风格、尊重对方边界。
- **不泄露聊天原文**；不在日志中输出完整内容；密钥与本地配置不入库。

## 回复辅助

当用户提供最新聊天截图或对方回复时：
1. 先读历史档案与最近对话，理解上下文与氛围；
2. 判断当前交流氛围（轻松/严肃/冷淡/试探）；
3. 给出 2~3 个自然回复，各附理由，保留用户原聊天风格；
4. 避免过度热情、刻意讨好、施加压力。

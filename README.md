# WeChat Relationship Analyzer

微信聊天记录提取与恋爱进度分析 Skill（OpenAI Agent Skill 格式）。

从微信聊天记录中提取结构化数据，分析双方关系所处阶段、互动模式、情绪变化与关键事件，
持续追踪关系进展，并基于上下文生成自然的回复建议。

> **隐私声明**：本工具仅处理用户主动提供或有权访问的数据，全程本地运行，不上传任何聊天内容。

## 功能

- 从微信数据库（需配合 `wcdb-key-tool` 解密）或导出文件（TXT/CSV/JSON/HTML）提取聊天记录
- 统一结构化数据：`timestamp / sender / receiver / message_type / content / source_file / source_reference`
- 客观统计：消息数、每日频率、谁主动、回复间隔、深夜聊天、对话中断
- 关系阶段识别（初识→暧昧→升温→稳定→降温，共 9 阶段，证据不足标不确定）
- 关键事件时间线提取
- 增量导入与历史状态对比（进度档案）
- 基于上下文生成回复建议
- 完整分析报告（状态/趋势/证据/建议）

## 目录结构

```
wechat-relationship-analyzer/
├── SKILL.md                       # 主指令（OpenAI Skill 格式）
├── README.md
├── config.example.json            # 配置模板（复制为 config.json 使用）
├── scripts/
│   ├── extract_structured.py      # 解密库 → 结构化 JSON
│   ├── parse_import.py            # TXT/CSV/JSON/HTML → 结构化 JSON
│   ├── statistics.py              # 结构化 JSON → 客观统计
│   └── merge_history.py           # 增量合并 + 历史对比
├── references/
│   ├── relationship_stages.md     # 关系阶段定义
│   ├── analysis_rules.md          # 反过度推断规则
│   └── report_template.md         # 报告模板
└── data/                          # 运行时输出（已 gitignore）
```

## 快速开始

### 前提

本技能只做「分析层」。要从微信数据库提取，需要先用
[`wcdb-key-tool`](https://github.com/)（或任意微信解密工具）把聊天记录解密为明文 SQLite。
如果你已经有导出的 TXT/CSV/JSON 文件，可跳过这一步，直接用 `parse_import.py`。

### 1. 配置

```bash
cp config.example.json config.json
# 编辑 config.json，填入 wcdb_tool_dir、self_username、target_username
```

### 2. 提取 + 统计

```bash
python3 scripts/extract_structured.py --config config.json --output data/messages.json
python3 scripts/statistics.py --input data/messages.json --output data/stats.json
```

### 3. 分析

把 `data/messages.json` + `data/stats.json` 交给 AI（配合 SKILL.md），
或直接让支持 Skill 的 Agent 加载本目录，按 SKILL.md 指令完成分析。

## 依赖

- Python 3.10+
- 仅从数据库提取时需要 `zstandard`（`pip install zstandard`）
- 仅从数据库提取时需要 `wcdb-key-tool` 目录（复用其 `export_chat.py` 解析逻辑）

## 数据隐私

- `data/` 目录、`config.json`、密钥文件均已在 `.gitignore` 中排除
- 聊天原文不会出现在日志里
- 分析只在本地产出，不经过任何第三方服务

## License

MIT

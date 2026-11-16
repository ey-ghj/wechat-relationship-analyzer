# WeChat Relationship Analyzer

微信聊天记录提取与恋爱进度分析 Skill（OpenAI Agent Skill 格式）。

从微信聊天记录中提取结构化数据，分析双方关系所处阶段、互动模式、情绪变化与关键事件，
**长期记忆关系背景、持续追踪关系进展、复盘关键事件**，并基于完整历史上下文生成自然的回复建议。

> **隐私声明**：本工具仅处理用户主动提供或有权访问的数据，全程本地运行，不上传任何聊天内容。

## 功能

- 从微信数据库（需配合 `wcdb-key-tool` 解密）、导出文件（TXT/CSV/JSON/HTML）或**截图 OCR** 提取聊天记录
- 统一结构化数据：`timestamp / sender / receiver / message_type / content / source_file / source_reference`
- 客观统计：消息数、每日频率、谁主动、回复间隔、深夜聊天、对话中断、**最近 7 天/30 天窗口对比**
- **长期关系记忆**：关系档案、阶段变化历史、重要事件时间线、用户行动与结果记录、统计快照
- **关键事件复盘**：提取事件前后上下文，分析背景/双方反应/后续行动/关系变化
- **个人聊天风格档案**：平均长度、表情占比、标点习惯、高频口头禅、时段分布
- 关系阶段识别（9 阶段，证据不足标不确定）
- 增量导入、去重、历史对比
- 数据备份与异常恢复、日志脱敏
- 基于历史上下文 + 个人风格的回复建议
- 完整分析报告（状态/趋势/证据/建议）

## 目录结构

```
wechat-relationship-analyzer/
├── SKILL.md                       # 主指令（OpenAI Skill 格式）
├── README.md
├── config.example.json            # 配置模板（复制为 config.json 使用）
├── scripts/
│   ├── extract_structured.py      # 解密库 → 结构化 JSON
│   ├── export_chat.py             # 消息解析（zstd/引用/链接/撤回，随包自带）
│   ├── parse_import.py            # TXT/CSV/JSON/HTML/截图 OCR → 结构化 JSON
│   ├── ocr.py                     # OCR 统一接口（macOS Vision / 其他平台 Tesseract）
│   ├── statistics.py              # 客观统计（含 7/30 天窗口）
│   ├── style.py                   # 聊天风格客观指标
│   ├── merge_history.py           # 增量合并 + 去重
│   ├── profile.py                 # 关系档案（长期记忆核心）
│   ├── events.py                  # 关键事件时间线 + 复盘
│   ├── backup.py                  # 数据备份与恢复
│   └── safe_log.py                # 日志脱敏
├── references/
│   ├── relationship_stages.md     # 关系阶段定义
│   ├── analysis_rules.md          # 反过度推断规则
│   ├── report_template.md         # 报告模板
│   ├── event_review.md            # 事件复盘指南
│   └── chat_style.md              # 聊天风格档案说明
├── .github/workflows/test.yml     # CI 自动测试
├── tests/                         # 单元测试
└── data/                          # 运行时输出（已 gitignore）
```

## 快速开始

### 前提

本技能只做「分析层」。要从微信数据库提取，需要先用
[`wcdb-key-tool`](https://github.com/TANGandXUE/wcdb-key-tool)（或任意微信解密工具）把聊天记录解密为明文 SQLite。
如果你已经有导出的 TXT/CSV/JSON 文件或聊天截图，可跳过这一步，直接用 `parse_import.py`。

### 1. 配置

```bash
cp config.example.json config.json
# 编辑 config.json，填入 wcdb_tool_dir、self_username、target_username
```

### 2. 提取 + 统计 + 风格

```bash
python3 scripts/extract_structured.py --config config.json --output data/messages.json
python3 scripts/statistics.py --input data/messages.json --output data/stats.json
python3 scripts/style.py --input data/messages.json --output data/style.json
```

### 3. 建立关系档案（长期记忆）

```bash
python3 scripts/profile.py init --config config.json --stats data/stats.json
```

### 4. 分析

按 `SKILL.md` 的记忆感知工作流，让 Agent 读取消息 + 统计 + 风格 + 档案，产出分析报告，
再用 `profile.py update` 写回结论，实现长期追踪。

## 依赖

- Python 3.10+
- 从数据库提取时需要 `zstandard`（`pip install zstandard`）
- OCR（可选）：
  - macOS：系统 Vision 框架（无需额外安装，需 Xcode Command Line Tools）
  - 其他平台：Tesseract（`brew install tesseract tesseract-lang` 或对应包管理器）
- 消息解析脚本 `export_chat.py` 已随本技能打包在 `scripts/` 目录，开箱即用

## 数据隐私与安全

- `data/`、`backups/`、`config.json`、密钥文件均已在 `.gitignore` 中排除
- 原始记录只读：脚本从不修改源数据库/源文件
- 日志脱敏：`safe_log.py` 掩码手机号/微信号
- 分析前备份、出错可恢复（`backup.py`）
- 分析只在本地产出，不经过任何第三方服务

## License

MIT

# B站评论分析器

本地运行的 Windows 桌面应用，用于采集 B 站公开视频评论并做情感倾向统计。数据仅保存在本机，不自动上传用户数据。

## 当前阶段

当前已完成**阶段 1~3**：项目骨架、数据库模型、BV 评论采集、标签批量搜索、播放量区间选择与断点续爬。后续阶段会加入情感分析、统计图表、UI 和打包。

## 技术栈

- Python 3.11
- PySide6
- SQLite + SQLAlchemy 2.x
- httpx
- pandas
- matplotlib
- PyInstaller

## 目录结构

```
main.py                     # 入口（当前仅初始化数据库）
bili_analyzer/
  config.py                 # 配置
  constants.py              # 枚举与常量
  db.py                     # Engine / Session / 建库
  models/                   # ORM 模型
  utils/                    # 日志、时间、脱敏、JSON
tests/                      # pytest
```

## 开发环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
pytest
```

## CLI 用法

```powershell
# 初始化数据库
.\.venv\Scripts\python.exe -m bili_analyzer.cli initdb

# 抓取单个 BV 评论（可选 --no-replies --max-pages N --cookie ...）
.\.venv\Scripts\python.exe -m bili_analyzer.cli crawl BVxxxxxx --max-pages 2

# 按标签批量抓取（配置示例见 docs/batch_config.example.json）
.\.venv\Scripts\python.exe -m bili_analyzer.cli crawl-tag --config-file batch.json
```

`crawl-tag` 的 JSON 配置示例：

```json
{
  "keyword": "标签名",
  "start_time": "2024-01-01T00:00:00",
  "end_time": "2024-12-31T23:59:59",
  "include_replies": true,
  "page_size": 20,
  "buckets": [
    {"bucket_key": "100_1000", "count": 5, "sort_by": "play", "max_pages": 2}
  ]
}
```

## 数据模型

主要表：`tasks`、`videos`、`users`、`comments`、`analysis_results`、`crawl_progress`、`settings`，以及任务与视频/评论的关联表 `task_videos`、`task_comments`。

去重键：视频 `bvid`、评论 `rpid`、用户 `mid`，均在数据库层建立唯一约束。

## 隐私与合规

- 只采集公开接口可访问的数据。
- 遵守频率限制，不绕过验证码或风控。
- 用户 `mid` 支持脱敏显示。
- 日志不记录 Cookie 与完整评论原文。

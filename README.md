# B站评论分析器

本地运行的 Windows 桌面应用，用于采集 B 站公开视频评论并做情感倾向统计。数据仅保存在本机，不自动上传用户数据。

## 当前阶段

当前已完成**阶段 1~6**：项目骨架、数据库模型、BV 评论采集、标签批量搜索、播放量区间选择与断点续爬、可插拔情感分析、统计分析与图表、PySide6 桌面 UI 与历史任务。后续阶段为测试与打包。

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

## 启动 GUI

```powershell
python main.py
```

首次启动会自动在 `data/` 下创建 SQLite 数据库。界面包含首页任务列表、采集配置、进度、分析结果、用户详情和设置六个页面。

## CLI 用法

```powershell
# 初始化数据库
.\.venv\Scripts\python.exe -m bili_analyzer.cli initdb

# 抓取单个 BV 评论（可选 --no-replies --max-pages N --cookie ...）
.\.venv\Scripts\python.exe -m bili_analyzer.cli crawl BVxxxxxx --max-pages 2

# 按标签批量抓取（配置示例见 docs/batch_config.example.json）
.\.venv\Scripts\python.exe -m bili_analyzer.cli crawl-tag --config-file batch.json

# 对任务评论做情感分析（--force 忽略缓存重新分析）
.\.venv\Scripts\python.exe -m bili_analyzer.cli analyze --task-id 1

# 输出统计结果（overview / transition / extremes）
.\.venv\Scripts\python.exe -m bili_analyzer.cli stats --task-id 1 --type overview --membership all
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

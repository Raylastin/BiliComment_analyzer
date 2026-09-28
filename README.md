# B站评论分析器

本地运行的 Windows 桌面应用，用于采集 B 站公开视频评论并做情感倾向统计。数据仅保存在本机，不自动上传用户数据。

## 当前阶段

当前为**阶段 1：项目骨架 + 数据库模型**。已包含：

- 项目目录结构
- SQLAlchemy 数据模型与 SQLite 初始化
- 配置、日志、时间、脱敏等基础工具
- 最小单元测试

后续阶段会依次加入评论采集、批量搜索、情感分析、统计图表、UI 和打包。

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

## 数据模型

主要表：`tasks`、`videos`、`users`、`comments`、`analysis_results`、`crawl_progress`、`settings`，以及任务与视频/评论的关联表 `task_videos`、`task_comments`。

去重键：视频 `bvid`、评论 `rpid`、用户 `mid`，均在数据库层建立唯一约束。

## 隐私与合规

- 只采集公开接口可访问的数据。
- 遵守频率限制，不绕过验证码或风控。
- 用户 `mid` 支持脱敏显示。
- 日志不记录 Cookie 与完整评论原文。


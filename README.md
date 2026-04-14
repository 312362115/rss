# rss-daily

每日新闻聚合器:本地每天 10:00 自动抓取 AI / 币圈 / 科技圈一手信息(X + HN + Reddit + RSS),LLM 分类打分,生成中文日报 Markdown 到 `daily/` 目录,`git push` 到本仓库。

打开 GitHub 上 [`daily/`](./daily/) 目录即可浏览最新日报。

## 文档

- 方案:[`docs/specs/2026-04-13-news-aggregator-design.md`](./docs/specs/2026-04-13-news-aggregator-design.md)
- 计划:[`docs/plans/2026-04-13-news-aggregator-plan.md`](./docs/plans/2026-04-13-news-aggregator-plan.md)
- 需求池:[`docs/backlog/INDEX.md`](./docs/backlog/INDEX.md)
- X 小号准备:[`docs/runbooks/x-account-setup.md`](./docs/runbooks/x-account-setup.md)

## 快速开始

```bash
# 1. Python 环境
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. xreach(X 抓取 CLI,已全局装过跳过)
npm install -g xreach-cli

# 3. 按 docs/runbooks/x-account-setup.md 准备 X 小号 + cookie

# 4. 手动跑一次
python src/main.py

# 5. 装 launchd 定时
./scripts/install_launchd.sh
```

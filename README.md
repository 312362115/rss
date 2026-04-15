# rss-daily

每日新闻聚合器,本地自动抓取 AI / 币圈 / 科技圈一手信息,LLM 分类打分,生成中文日报 Markdown 到 `daily/` 目录,`git push` 到本仓库。

**抓取频率分层(2026-04-15 起)**:
- **X hourly**:每天 10/14/18 三次触发,产出时间线切片 `daily/YYYY/MM/DD/HH.md`
- **daily 源**(HN / Reddit / RSS / GitHub Trending):每天首次 run 跑一次,产出今日精选 + 热门开源项目,合并到日级索引 `daily/YYYY/MM/DD.md`(若首次 run 挂了,下一次 run 自愈补跑)

打开 GitHub 上 [`daily/`](./daily/) 目录即可浏览最新日报:日级索引页包含今日精选 + GitHub Trending + 顶部的 X 时段链接。

## 文档

- 方案:[`docs/specs/2026-04-13-news-aggregator-design.md`](./docs/specs/2026-04-13-news-aggregator-design.md)(架构)
- 频率分层方案:[`docs/specs/2026-04-15-schedule-layering-design.md`](./docs/specs/2026-04-15-schedule-layering-design.md)
- 需求池:[`docs/backlog/INDEX.md`](./docs/backlog/INDEX.md)
- 回归用例:[`docs/tests/schedule-layering.md`](./docs/tests/schedule-layering.md)
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

# 4. 手动跑一次(可选 --no-push / --daily-only / --hourly-only / --force-daily)
.venv/bin/python -m src.main --no-push

# 5. 装 launchd 定时
./scripts/install_launchd.sh
```

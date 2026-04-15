# 抓取频率分层 — 回归测试用例

> 关联方案: `docs/specs/2026-04-15-schedule-layering-design.md`
> 关联计划: `docs/plans/2026-04-15-schedule-layering-plan.md`

测试入口都用 `.venv/bin/python -m src.main`,需要在仓库根目录执行。

---

## 用例 1: config 加载完整

- **执行命令**: `.venv/bin/python -m src.config`
- **预期**: 输出包含
  - `schedules = {'x': 'hourly', 'hackernews': 'daily', 'reddit': 'daily', 'rss': 'daily', 'github_trending': 'daily'}`
  - `github_trending = {'since': 'daily', 'top_n': 15}`
  - `hotness_caps.github_star_delta = 500`

## 用例 2: GitHub Trending 单源抓取

- **执行命令**: `.venv/bin/python -m src.fetch.github_fetcher`
- **预期**:
  - 输出 `=== N items ===`,N ≥ 5(trending 当天通常 15-25 条)
  - 每条含 `+X★` star_delta、仓库 slug、`norm=...` 归一化分数
  - 无 traceback

## 用例 3: X 跨 slot 去重幂等性

- **执行命令**:
  ```bash
  .venv/bin/python -c "
  from src.dedup import filter_x_seen, X_SEEN_PATH
  from src.fetch.base import Item
  from datetime import datetime
  X_SEEN_PATH.unlink(missing_ok=True)
  mk = lambda s, i: Item(source=s, id=i, url=f'https://x.com/a/{i}', url_hash=i, title='t', text='', author='a', published_at=datetime.now())
  print('round1:', [(i.source, i.id) for i in filter_x_seen([mk('x','1'), mk('x','2'), mk('hn','3')])])
  print('round2:', [(i.source, i.id) for i in filter_x_seen([mk('x','1'), mk('x','4'), mk('hn','5')])])
  X_SEEN_PATH.unlink(missing_ok=True)
  "
  ```
- **预期**:
  - round1: `[('x','1'), ('x','2'), ('hn','3')]`
  - round2: `[('x','4'), ('hn','5')]` — `x/1` 被去重过滤

## 用例 4: render 三件套(skeleton / x_links / daily / x_slice)

- **执行命令**: `.venv/bin/python -m src.render`
- **预期**: 依次输出 4 段示例:
  - skeleton 含 `<!-- X_LINKS_BEGIN -->` 和 `<!-- DAILY_BEGIN -->` 占位
  - X 链接行格式 `> 📊 今日 X 时间线:[10:00](15/10.md) · [14:00](15/14.md)`
  - daily 段含三类 + GitHub Trending 列表
  - x_slice 含 `# YYYY-MM-DD HH:00 X 时间线` 标题 + 返回链接 + 三类

## 用例 5: 端到端 daily-only run(强制重写,不 push)

- **前置**: 当天 `daily/YYYY/MM/DD.md` 可有可无
- **执行命令**: `.venv/bin/python -m src.main --daily-only --no-push --force-daily`
- **预期**:
  - 日志含 `daily fetched N raw items`、`daily after dedup`、`ranking N items in M batches`
  - 日志含 `wrote daily section to daily/.../DD.md`
  - 文件 `daily/YYYY/MM/DD.md` 的 `<!-- DAILY_BEGIN -->` 块被填充,含 `## 今日精选` + `## 今日热门开源项目`
  - 退出码 0

## 用例 6: 端到端 hourly run(只 X,不 push)

- **前置**: xreach CLI 已配置 cookie
- **执行命令**: `.venv/bin/python -m src.main --hourly-only --no-push`
- **预期**:
  - 日志含 `hourly fetched N raw items`、`x_seen filter: ...`、`wrote x slice ...`
  - 生成 `daily/YYYY/MM/DD/HH.md`(HH 为当前 slot)
  - `daily/YYYY/MM/DD.md` 的 `<!-- X_LINKS_BEGIN -->` 块被刷新含当前 slot 链接

## 用例 7: 自愈跳过(daily 已存在则跳过)

- **前置**: 当天已跑过 daily(`daily_section_exists` 返回 True)
- **执行命令**: `.venv/bin/python -m src.main --daily-only --no-push`(不带 --force-daily)
- **预期**:
  - 日志含 `daily section already exists for YYYY-MM-DD, skip`
  - **不**触发 fetch、不调 LLM
  - 退出码 1(因为 total ranked = 0)

## 用例 8: X 切片硬截断

- **目的**: 验证 `x_fetcher.py` 修复的分页超 cap 问题
- **执行命令**:
  ```bash
  .venv/bin/python -c "
  from src.fetch.x_fetcher import XFetcher
  from src.config import load
  cfg = load()
  f = XFetcher(lists=cfg.x.get('lists', [])[:1], users=[], delay_ms=1500, x_favorites_cap=10000)
  items = f.fetch()
  print(f'fetched {len(items)} items, cap was 50')
  assert len(items) <= 50, f'EXCEEDED CAP: {len(items)}'
  print('OK')
  "
  ```
- **预期**: `fetched N items, cap was 50` 且 N ≤ 50,最后输出 `OK`

## 用例 9: .gitignore 含 .cache/

- **执行命令**: `grep -n '\.cache' .gitignore`
- **预期**: 命中一行 `.cache/`,`.cache/x_seen.json` 不会被 git 追踪

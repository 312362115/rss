# 抓取频率分层 + GitHub Trending 接入 — 技术方案

> 关联 backlog: `docs/backlog/2026-04-14-schedule-layering.md`
> 启动日期: 2026-04-15

## 背景与动机

**2026-04-14 复盘触发**: 当天恢复每 4h 一更(10/14/18),发现两类问题。

1. **重复率问题**: 除 X 外,其他源在 4h 窗口内基本无新增 — HN top 挂几小时不变,Reddit `t=day` 是 24h 滑动窗口,RSS 媒体半天才一篇,GitHub Trending 一天才刷新。同一批条目被反复抓 3 次、反复送 LLM 打分 3 次、反复塞进日报,信号增量为 0、LLM 成本 ×3。
2. **X 分页超 cap**: 18:00 实测 `tweets_per_run: 50` 实抓 99/91 条,xreach 按页滚动时 limit 没严格截断。

同时新需求: **想加 GitHub Trending 数据源**(daily top 15)。如果继续"每 4h 全量抓",这个天然 daily 的源会被反复抓 3 次,凸显架构问题。

**核心洞察**: 这 4 个问题(恢复高频更新、跨 slot 去重、加 GitHub Trending、源级频率不同)本质是同一个架构缺失 — **抓取频率应该按源分层,不是按 launchd 的全局周期一刀切**。

## 现状分析

- `src/main.py::run()` 每次执行 = 全量跑所有 fetcher(`build_fetchers()` 无条件加载 X/HN/Reddit/RSS),没有"按需跑"概念
- `src/publish.py::write_slot()` 把所有 slot 写到同一个 `daily/YYYY/MM/DD.md`,一篇 MD 装 3 个时段的全部内容
- `src/dedup.py::dedup_in_slot()` 只做单 slot 内跨源去重,无跨 slot 状态
- `sources.yaml` 没有 `schedule` 字段,频率决策完全在 launchd 层
- `src/fetch/x_fetcher.py` xreach CLI limit 不严格,产出可能超 cap

不改的后果: LLM 成本翻倍、日报全是重复信号、GitHub Trending 没法干净接入。

## 调研与备选方案

### 方案 A: 每源 TTL 缓存
fetcher 内部缓存 N 小时,过期才重新抓。
- 优点: 通用、自动
- 缺点: 缓存命中后还是要走 dedup + rank,LLM 成本节省有限;缓存失效语义复杂
- 结论: 复杂度换的收益不够

### 方案 B: yaml 配置 `schedule: hourly|daily`,调度层按需触发(选用)
源的频率下沉到 yaml,`main.py::run()` 按当前 run 的"是否首次/是否已有 daily 分区"决定跑哪些 fetcher。
- 优点: 决策点清晰、配置即文档、新增源直接标 `schedule` 即可
- 缺点: 调度逻辑需要感知"daily 是否已写过"
- 验证: 用 daily MD 文件中是否存在 `<!-- DAILY_BEGIN -->` marker 作为状态判断,无需额外存储
- 结论: 选用

## 决策与取舍

**采用方案 B**: 频率字段下沉到 `sources.yaml`,`main.py` 按 marker 判断 daily 是否已跑过、自愈补跑。

### 4 个待定决策的对齐结果(2026-04-15 与用户确认)

| 决策点 | 选定方案 |
|--------|----------|
| launchd 触发频率 | 维持 10/14/18 每天 3 次 |
| daily 触发时机 | 当天首次 run 自愈补跑(10:00 挂了 14:00 补) |
| X 切片分类策略 | 按 AI/币圈/科技 分组(和今日精选一致) |
| 15.md 顶部 X 链接更新 | 每次 X run 追加 |

`top_n_per_category` 暂不分层,daily 和 X 切片都用现有的 20。

## 技术方案

### 1. sources.yaml: 加 `schedule` 字段 + GitHub Trending

```yaml
x:
  schedule: hourly        # 每次 run 都抓
  # ... 原有配置

hackernews:
  schedule: daily

reddit:
  schedule: daily

rss:
  schedule: daily

github_trending:
  schedule: daily
  since: daily
  top_n: 15
  # 归一化封顶
hotness_caps:
  github_star_delta: 500   # 加进 meta.hotness_caps
```

### 2. 调度逻辑改造(`src/main.py`)

```python
def run(*, push=True, include_x=True):
    cfg = load()
    today = ...

    # 1. 永远跑 hourly 源(X)
    hourly_items = fetch_all(build_fetchers(cfg, schedule="hourly", include_x=include_x))
    process_and_write_x_slot(hourly_items, today, slot)   # 写 daily/YYYY/MM/DD/HH.md

    # 2. 检查当天 daily 是否已写过
    if not daily_section_exists(today):
        daily_items = fetch_all(build_fetchers(cfg, schedule="daily"))
        process_and_write_daily(daily_items, today)        # 写 daily/YYYY/MM/DD.md

    git_publish(...)
```

`build_fetchers()` 增加 `schedule` 参数,按字段过滤。`daily_section_exists()` = `<!-- DAILY_BEGIN -->` 在当日索引文件里出现。

### 3. 日报产物结构(形态 C: 拆文件 + 日级索引)

物理结构:
```
daily/2026/04/
├── 15.md              # 日级索引 + 今日精选 + GitHub Trending(daily 1 次)
└── 15/                # X 时间线切片子目录
    ├── 10.md          # X @ 10:00
    ├── 14.md          # X @ 14:00
    └── 18.md          # X @ 18:00
```

**`15.md`**(日级索引):
```markdown
# 2026-04-15

> 📊 今日 X 时间线:[10:00](15/10.md) · [14:00](15/14.md) · [18:00](15/18.md)

<!-- DAILY_BEGIN -->
## 今日精选

### AI
1. **[标题](url)** — 来源 · score
   - 点评:...
### 币圈
...

## 今日热门开源项目(GitHub Trending)
1. **[owner/repo](https://...)** — +500 stars today
   - 点评:...
<!-- DAILY_END -->
```

**`15/HH.md`**(X 切片):
```markdown
# 2026-04-15 HH:00 X 时间线

> ← [返回今日精选](../15.md)

## AI
...
## 币圈
...
## 科技
...
```

**关键设计**:
- 顶部 X 链接列表: 每次 X run 时,扫描 `15/` 子目录已有切片重写 `> 📊` 行(append 等价于"重新扫描"),实现简单且天然幂等
- 旧格式 `daily/2026/04/14.md` 等保留不迁移,新架构从 2026-04-15 生效
- `<!-- DAILY_BEGIN -->` 既是标记也是判断 daily 是否已跑的依据

### 4. X 跨 slot 去重

只 X 需要(其他源 daily 天然去重)。极简实现:

- `.cache/x_seen.json`: `{tweet_id: first_seen_unix_ts}`
- TTL 48h(覆盖跨自然日边界)
- 粒度: 直接 tweet `id`,不用 url_hash
- 时机: X fetch 后、`dedup_in_slot` 前
- 清理: 每次 run 开始扫一遍删过期
- `.gitignore` 加 `.cache/`

### 5. GitHub Trending Fetcher

新增 `src/fetch/github_fetcher.py`,抓 https://github.com/trending?since=daily HTML,BeautifulSoup 解析(`bs4` 已在依赖)。

数据映射:
| Item 字段 | 来源 |
|----------|------|
| `source` | `"github"` |
| `id` | `"{owner}/{repo}"` |
| `url` | `https://github.com/{owner}/{repo}` |
| `title` | `{owner}/{repo}` |
| `text` | 仓库描述 |
| `author` | `owner` |
| `published_at` | run 时间(trending 没有发布时间) |
| `raw_score` | 当日新增 star(解析 "X stars today") |
| `normalized_score` | `min(raw/500, 1) * 30` |

`base.py::Source` literal 加 `"github"`,`SOURCE_PRIORITY` 加 `{"github": 1}`(同 HN 级)。

### 6. X 分页超 cap 修复

排查 `src/fetch/x_fetcher.py`:
1. xreach CLI 调用是否传了 limit / `--max-pages`
2. 传了是否生效
3. 不严格截断的话,fetcher 内对每个 list 结果硬截断 `[:tweets_per_run]`

顺便查 ai-core 为什么只抓到 41(< 50 cap),是 list 不活跃还是分页提前终止。

### 7. publish/render 改造点

- `render.py`: 新增 `DAILY_BEGIN/DAILY_END` marker,新增 `render_daily_section()` 渲染今日精选 + GitHub Trending,新增 `render_x_slice_file()` 渲染 X 切片完整文件(替代 `render_slot_section`)
- `publish.py`: 新增 `daily_index_path(d)` / `x_slice_path(d, slot)`,`write_x_slice()` 写独立切片文件,`write_daily_section()` 写日级索引,`refresh_x_links_in_index(d)` 扫描 `15/` 目录重写顶部 X 链接行
- `templates/`: 新增 `daily.md.j2`(今日精选 + GH trending) 和 `x_slice.md.j2`,旧 `slot.md.j2` 保留兼容旧文件

## 风险与边界

| 风险 | 缓解 |
|------|------|
| `daily_section_exists` 误判 | marker 用 HTML 注释,grep 字符串精确匹配,不会与正文冲突 |
| GitHub trending HTML 变更导致解析失败 | fetcher 失败不影响其他源(`fetch_all` 已做 try/except);单独写一份 `docs/tests/github-trending.md` 做回归 |
| X 跨 slot 去重把"早上看过、下午又有人转的"过滤掉 | 这是有意为之,真正的"再次火"会出现在 daily 源中 |
| 日级索引顶部 X 链接重写竞态(同一时刻两个 run) | launchd 不会并发触发,且 publish 内部串行写文件 |
| .cache/ 在 push 时被误提交 | `.gitignore` 加 `.cache/` |

## 非目标

- 不做每源 TTL 缓存
- 不做跨天历史去重(daily 每天独立)
- 不引入 GitHub 官方 API
- 不做内容相似度去重
- 不迁移旧日报(`daily/2026/04/14.md` 等保留)

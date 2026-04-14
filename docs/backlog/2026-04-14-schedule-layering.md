---
priority: P2
status: open
spec:
plan:
---

# 抓取频率分层:X 小时更 + 其他日更 + GitHub Trending 接入

## 背景

**2026-04-14 复盘触发**:当天尝试每 4h 一更新(10:00 / 14:00 / 18:00),发现两类问题:

1. **重复率问题**:除 X 外,其他源在 4h 窗口内几乎没有新增(HN top 挂几小时,Reddit `t=day` 是 24h 滑动窗口近乎不变,RSS 媒体 blog 半天一篇,GitHub Trending 每天才刷新一次)。4h 跑一次 → 同一批条目被反复抓取、反复送 LLM 打分、反复塞进日报,信号增量为 0
2. **X 分页超 cap**:18:00 实测 crypto-core / tech-core 配置 `tweets_per_run: 50` 实抓 99/91 条,xreach 按页滚动时 limit 没严格截断

同时有个新需求:**想加 GitHub Trending 数据源**,daily 榜单 top 15。但如果继续"每 4h 全量抓"的架构,GitHub Trending 作为一个天然 daily 更新的源会被重复抓 3 次,更凸显架构问题。

**核心洞察**:这 4 个问题(恢复高频更新、跨 slot 去重、加 GitHub Trending、源级频率不同)本质都是一个架构缺失——**抓取频率应该按源分层**,不是按 launchd 的全局周期一刀切。

## 目标

1. 恢复 4h 一更新(甚至更密),但**只有 X 真的每次跑**
2. HN / Reddit / RSS / GitHub Trending 每天只抓 1 次,产出"今日精选"分区
3. 每天的日报 MD 顶部是日更"今日精选",下面倒序是 X 小时更"时间线切片",两类信号性质不同不再混淆
4. 顺手修掉 X 分页超 cap

## 方案

### 1. 数据源分层配置

`sources.yaml` 每个源加 `schedule` 字段:

```yaml
x:
  schedule: hourly        # 每次 run 都抓
  # 原有配置保持...

hackernews:
  schedule: daily         # 只在当天第一次 run 抓

reddit:
  schedule: daily

rss:
  schedule: daily

github_trending:          # 新增
  schedule: daily
  since: daily
  top_n: 15
```

### 2. 调度逻辑(main.py)

- `launchd` 恢复多次触发(待定:10/14/18 还是更密)
- 每次 run 进来:
  1. 永远跑 `schedule: hourly` 的源
  2. 检查当天 MD 文件是否已有 daily 分区(用新 marker `<!-- DAILY_BEGIN -->`)
     - 没有 → 跑 `schedule: daily` 的源,写入 daily 分区
     - 已有 → 跳过 daily 源(省 LLM 成本)

**自愈性**:如果 10:00 的 run 挂了,14:00 的 run 发现当天还没 daily 分区也会补跑。不会出现"当天没日更"的空洞

### 3. 日报产物结构改造(形态 C:拆文件 + 日级索引)

物理结构:

```
daily/2026/04/
├── 15.md              # 日级索引 + 今日精选(日更 1 次)
└── 15/                # 子目录,X 时间线切片
    ├── 10.md          # X @ 10:00
    ├── 14.md          # X @ 14:00
    └── 18.md          # X @ 18:00
```

`15.md`(日级索引 + 今日精选):

```markdown
# 2026-04-15

> 📊 今日 X 时间线:[10:00](15/10.md) · [14:00](15/14.md) · [18:00](15/18.md)

## 今日精选

### AI
1. **[标题](url)** — 来源 · score
   - 点评:...
### 币圈
...
### 科技
...

## 今日热门开源项目(GitHub Trending)
1. **[owner/repo](https://...)** — +500 stars today
   - 描述 / 点评
2. ...
```

`15/18.md`(X 时间线切片,独立文件):

```markdown
# 2026-04-15 18:00 X 时间线

> ← [返回今日精选](../15.md)

## AI
1. **[@sama: 推文标题](https://x.com/...)** — 2.3k likes
   - 点评:...
### 币圈
...
### 科技
...
```

**关键设计**:
- 日级索引页(`15.md`)的顶部是 X 时间线链接列表,每次 X run 完后追加一项(或替换占位符)
- `15.md` 主体是"今日精选 + GitHub Trending",每天写一次,稳定
- `15/HH.md` 是独立文件,每个 X run 写一份,文件名就是 slot 时间
- 旧格式 `daily/2026/04/14.md` 等**保留不迁移**,新格式从第一次执行新方案的那天开始生效

### 4. X 跨 slot 去重(缩小版)

只有 X 需要跨 slot 去重(其他源已经通过 daily 机制天然去重了)。实现可以极简:

- `.cache/x_seen.json`:`{tweet_id: first_seen_ts}`
- TTL:48h(足够覆盖跨两个自然日的边界)
- 粒度:**直接按 tweet `id`**,不用 url_hash(X fetcher 拿到的 id 就是唯一的)
- 过滤时机:X fetch 之后、dedup_in_slot 之前
- 清理:每次 run 开始扫一遍,删 `first_seen_ts < now - 48h`

代码量比原计划的通用 URL 去重小一半。

### 5. GitHub Trending Fetcher

抓 https://github.com/trending?since=daily 的 HTML,BeautifulSoup 解析。需要:

- 新增 `src/fetch/github_fetcher.py`
- `base.py::Source` literal 加 `"github"`
- `base.py::SOURCE_PRIORITY` 加 `{"github": 1}`(跟 HN 同级)
- `sources.yaml::hotness_caps` 加 `github_star_delta: 500`

数据映射:

| Item 字段 | 来源 |
|----------|------|
| `source` | `"github"` |
| `id` | `"{owner}/{repo}"` |
| `url` | `https://github.com/{owner}/{repo}` |
| `title` | `{owner}/{repo}` |
| `text` | 仓库描述 |
| `author` | `owner` |
| `raw_score` | 当日新增 star("X stars today") |
| `normalized_score` | `min(raw/500, 1) * 30` |

### 6. X 分页超 cap 修复

排查 `src/fetch/x_fetcher.py`:
- xreach CLI 调用有没有传 limit / `--max-pages`
- 传了是否生效
- 如果 xreach 不严格截断,在 fetcher 内对每个 list 结果硬截断 `[:tweets_per_run]`

顺便查 ai-core 为什么只抓到 41(< 50 cap),是 list 本身不活跃还是分页提前终止。

## 待定决策

启动任务前需要对齐:

- **launchd 触发频率**:10/14/18(每天 3 次) vs 10/13/16/19/22(每天 5 次) vs 更密
- **daily 触发时机**:"当天第一次 run 自愈补跑"(推荐,10:00 挂了 14:00 自动补) vs "只在 10:00 专用"
- **top_n_per_category 是否分层**:日更用 20 / X 切片用 10,还是都 20
- **X 切片的分类策略**:按 AI/币圈/科技 分组(和日更一致),还是直接按时间序平铺
- **15.md 顶部 X 链接列表更新机制**:每次 X run 追加(append) vs 一天固定三个占位符(10:00 写入时全部生成,后续 run 替换锚点)

## 非目标

- 不做每源 TTL 缓存(简化为 hourly/daily 二元)
- 不做跨天历史去重(daily 每天独立一份)
- 不引入 GitHub 官方 API(用 trending 页面 scrape,trending 没有官方 API)
- 不做内容相似度去重(只按 tweet id)
- **不迁移旧日报**:`daily/2026/04/14.md` 等老格式文件保留不动,新架构从启动任务那天开始生效

## 预期收益

1. **LLM 成本降一半**:daily 分区每天打分 ~200 条(1 次),X 每次 ~200-300 条。14:00/18:00 只打分 X,比原来快一半
2. **信号质量升**:用户打开日报,顶部是"今日全网精选"(稳定),下面是"X 时间线切片"(增量),两类信号分离
3. **架构更诚实**:频率决策下沉到 yaml,以后想调哪个源的频率改一行配置即可
4. **GitHub Trending 天然接入**:zero overhead 新增,直接标 `schedule: daily`

## 关联文件

需要改动:
- `sources.yaml` — 加 `schedule` 字段、加 `github_trending`
- `src/main.py` — `run()` 改调度逻辑,按 schedule 过滤 fetcher
- `src/fetch/base.py` — `Source` 扩展、`SOURCE_PRIORITY` 扩展
- `src/fetch/github_fetcher.py` — 新增
- `src/fetch/x_fetcher.py` — 修分页超 cap
- `src/dedup.py` — 加 X 级别的 `.cache/x_seen.json` 去重
- `src/render.py` — 加 daily section 渲染 + marker 常量
- `src/publish.py` — 支持写入 daily 分区的逻辑
- `src/templates/` — 新增 daily section 模板
- `launchd/com.renlongyu.rss.plist` — 恢复多次触发
- `.gitignore` — 加 `.cache/`
- `docs/specs/2026-04-13-news-aggregator-design.md` — 同步新架构
- `README.md` — 同步频率描述

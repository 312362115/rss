---
priority: P2
status: open
spec:
plan:
---

# 跨 slot 去重 + X 分页超量

## 背景

当前 `src/dedup.py` 只做单次运行内的 URL 去重(`dedup_in_slot`),注释明确写"每次运行独立,无持久化"。这导致把 launchd 设成一天多次(4h 一更新)时,相邻两次运行会大量重复抓到同一批条目(X list 新 tweet 量 < cap、Reddit `t:day` top、HN 头条挂几小时、RSS 站点更新慢),所以 2026-04-14 把频率改回每天 1 次(10:00)。

想恢复 4h 一更新的前提:必须做**跨 slot 本地去重**。

另外 2026-04-14 18:00 跑批时发现 X 抓取量超配置一倍(crypto-core 99 / tech-core 91,配置 `tweets_per_run: 50`),推测是 xreach 按页滚动时 limit 没严格截断,或 fetcher 收到结果没做硬截断。

## 需求

### 1. 跨 slot 去重(P2,主项)

目标:同一 URL 在 TTL 窗口内只出现在一次日报里。

待定决策:
- **存储介质**:`.cache/seen.json`(简单) vs SQLite(更稳)。倾向 JSON,量级 ~千条/天,足够
- **TTL 窗口**:12h / 24h / 48h,默认先 24h
- **粒度**:按 `url_hash` 还是 `(url_hash, source)`?倾向只按 `url_hash`,跨源同一内容也不重复
- **过滤时机**:抓完之后、打分之前(避免浪费 LLM token)
- **清理策略**:每次运行开始时扫一遍,删掉 `first_seen_ts < now - TTL` 的条目
- **Race 风险**:单机 launchd 不会并发跑,忽略

需要同步改的地方:
- `src/dedup.py`:加 `load_seen() / save_seen() / filter_seen()`
- `src/main.py`:在 `dedup_in_slot` 后、`rank` 前调用
- `.gitignore`:加 `.cache/`
- `docs/specs/2026-04-13-news-aggregator-design.md` §5.4.2:更新去重小节,说明跨 slot 策略
- 恢复 launchd plist 到每天 3 次(10:00 / 14:00 / 18:00)
- README / spec 里的频率描述同步改回

### 2. X 分页超量(P2,小项)

排查 `src/fetch/x_fetcher.py`:
- xreach CLI 调用有没有传 limit / `--max-pages`
- 传了是否生效
- 如果无法让 xreach 严格截断,在 fetcher 内对每个 list 结果硬截断 `[:tweets_per_run]`

顺便验证 list cookie / 账号状态是否稳定(ai-core 只抓到 41 条,小于 50 上限,可能是 list 本身不活跃,也可能是分页提前终止)。

## 非目标

- 不做跨天"已发日报归档去重"。每天 10:00 那次仍然不过滤任何历史,保证日报完整
- 不引入数据库。JSON 足够
- 不做内容相似度去重(文本级)。只按规范化 URL

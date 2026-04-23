# 2026-04-23 跨日持久去重

## 背景

用户反馈:日报中某些条目连续多日重复出现。定位后发现经典案例:
`anthropic.com/news/claude-opus-4-7` 这一 URL 在 04-17 与 04-23 两次出现在日报里。

根因:`src/dedup.py` 最初只为 X(Twitter)设计了 48h 跨 slot 缓存
(`.cache/x_seen.json`,key 为 tweet id),其余源(HN / Reddit / RSS / Web / GitHub)
**完全没有跨日持久去重**。日报每天跑一次,缓更源(企业官博、官网 News、HF Papers
等)会反复吐出同一条最新文章,日报就反复输出同一条。

## 决策

统一用单一缓存 `.cache/seen.json` 做跨 slot / 跨日去重,所有源共用:

- **Key**:`url_hash`(已有字段,所有源都带)
- **TTL**:**14 天**
- **作用点**:`filter_seen` 调用放在 `dedup_in_slot` **之后**,保证多源同 URL 时
  记录的是优先级最高的那条
- **force 旁路**:`--force-daily` 时调 `filter_seen(items, filter_out=False)`,
  即不过滤但仍写入缓存 —— 避免强制重写的条目明天常规 run 再次出现

## 取舍

### TTL=14 天的理由

- 48h(X 原值)对缓更源不够:Anthropic 类官网更新 < 1 篇/周,48h 后仍可能上榜
- 30 天过长:企业博客改版或重要文章真要重推时,被长时间屏蔽代价太高
- 14 天是一个"看得见的半月期"折中:覆盖常见的缓更节奏,误伤可控

### 放弃"按源分层 TTL"(如 X 48h / 其他 14d)

- 会引入两套缓存文件或复杂 schema,对 MVP 不值
- X 已有 `filter_seen` + `dedup_in_slot` + 源自身 list_id 约束,14 天对 X 影响几乎
  为零(重刷同 tweet URL 14 天内极少发生,且真发生了也合理地被压掉)

### 放弃"无限期去重"

- 一次误发就永久屏蔽文章,风险不对称
- 缓存文件会无界增长

### 旧 `.cache/x_seen.json` 作废

- 旧文件 key 是 tweet id,新逻辑 key 是 url_hash,schema 不兼容
- 不写迁移代码:旧文件首次运行后自然不被读取,等同于"冷启动 14 天窗口"
- 代价:过去 48h 内的 tweet URL 可能在过渡期的首次 hourly run 里被重新过一遍
  `dedup_in_slot`,影响可忽略
- 建议操作者在部署本次改动后手动 `rm .cache/x_seen.json`(非必须)

## 涉及改动

- `src/dedup.py`:`filter_x_seen` → `filter_seen`(通用),缓存路径与 TTL 常量
- `src/main.py`:`run_daily` 新增 `filter_seen` 调用(force 时 `filter_out=False`);
  `run_hourly` 调整顺序为 `dedup_in_slot → filter_seen`
- `tests/test_dedup.py`:新增 `TestFilterSeen` 覆盖 TTL / 跨源 / force / 缓存损坏
- `docs/tests/cross-day-dedup.md`:回归清单

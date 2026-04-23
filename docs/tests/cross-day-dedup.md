# 跨日去重回归用例

覆盖 `src/dedup.py` 的 `filter_seen` 与 `run_daily` / `run_hourly` 中的接入。

## 自动化

```bash
.venv/bin/python -m pytest tests/test_dedup.py -v
```

## 用例 1:第一次运行,全部通过 + 写入 seen.json

- **前置**:`.cache/seen.json` 不存在
- **步骤**:`filter_seen([item_a, item_b])`
- **预期**:返回两条;`seen.json` 写入 2 个 key

## 用例 2:第二次运行,同 URL 被过滤

- **前置**:用例 1 跑完后
- **步骤**:再次 `filter_seen([item_a])`
- **预期**:返回 0 条

## 用例 3:TTL 过期后重新放行

- **步骤**:冻结 `time.time=1000`,写入 item_a;推进至 `1000 + 15*86400`(超 14 天),再次过滤
- **预期**:返回 1 条(过期 key 已被清理)

## 用例 4:--force-daily 模式旁路但仍记录

- **前置**:item_a 已在 seen 中
- **步骤**:`filter_seen([item_a], filter_out=False)`
- **预期**:返回 1 条;下次常规 `filter_seen([item_a])` 返回 0 条

## 用例 5:utm 变体共享 seen

- **步骤**:`filter_seen([item_with_utm])` → `filter_seen([item_without_utm])`
- **预期**:第二次返回 0 条(normalize_url 统一了 key)

## 用例 6:跨源同 URL,第一次吃到就锁住

- **步骤**:先 `filter_seen([x_item])`,再 `filter_seen([rss_item])`(同 URL)
- **预期**:第二次返回 0 条

## 用例 7:缓存损坏自恢复

- **前置**:把 `.cache/seen.json` 写入非 JSON 文本
- **步骤**:`filter_seen([item_a])`
- **预期**:不抛异常,按空缓存起步,item_a 通过

## 端到端手测(手动触发)

```bash
# 1. 清掉本地缓存 + 今日日报已写的 DAILY 段(如需)
rm -f .cache/seen.json

# 2. force 重跑,填充 seen
.venv/bin/python -m src.main --no-push --daily-only --force-daily

# 3. 立即再跑一次常规 daily(不 force)
.venv/bin/python -m src.main --no-push --daily-only
# 预期:日志中 "no new items after cross-slot dedup, skip publish"
```

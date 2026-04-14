# news-aggregator 端到端回归测试

> 开发过程中积累的验证脚本和 smoke test,整理为可重复执行的回归用例。改动后按 Level 1/2/3 顺序跑完即可判断有无回归。

## 测试分级

| 级别 | 跑什么 | 耗时 | 何时跑 |
|------|--------|------|--------|
| L1 单元 | `pytest tests/` | <1s | 每次代码改动后 |
| L2 单源 smoke | 各 fetcher `python -m` smoke | 10-30s | fetcher 改动后 |
| L3 端到端 | `python -m src.main --no-push` | 3-5 min | 主流程改动后 / 上线前 |

---

## L1 — 单元测试

**命令**:
```bash
.venv/bin/pytest tests/ -v
```

**通过标准**:50/50 passed

**覆盖**:
- `test_dedup.py` — URL 规范化 + `dedup_in_slot` 优先级(13)
- `test_x_fetcher.py` — mock subprocess,parse_tweet 容错(8)
- `test_rank.py` — JSON 容错、id 对齐、LLM 漏条 fallback、关键词启发式(14)
- `test_render.py` — skeleton、三分类、空状态、倒序插入、4h 对齐(9)
- `test_publish.py` — 幂等、dry-run、git mock(7 — 回归时先过)

**已知不稳定**:无

---

## L2 — 单源 smoke(活水)

各 fetcher 的 `__main__` block 直连真实网络,验证源可用性。

### HN

```bash
.venv/bin/python -m src.fetch.hn_fetcher
```
**预期**:返回 ≥10 条,带真实 title + url + score,normalized_score 在 0-30 之间。

### Reddit

```bash
.venv/bin/python -m src.fetch.reddit_fetcher
```
**预期**:返回 ≥20 条(前 3 个 sub),HTTP 200,无 429。若出现 429,检查 `meta.reddit_user_agent` 是否配置自定义 UA。

### RSS

```bash
.venv/bin/python -m src.fetch.rss_fetcher
```
**预期**:返回 ≥10 条,部分 feed 可能 bozo 降级但不中断。

**已知问题**(不修不阻塞):
- `anthropic.com/news/rss.xml` — XML 非良构
- `huggingface.co/papers/feed/daily` — 语法错
- `newsletter.banklesshq.com` — SSL hostname 不匹配

### X(需要 cookie 就绪)

```bash
# 前提:xreach auth check 返回 ✓,sources.yaml 里 list_id 已填真实值
.venv/bin/python -m src.fetch.x_fetcher
```
**预期**:返回 ≥20 条。如果 cookie 过期,报错 "auth failed",走 `docs/runbooks/x-account-setup.md` 的 Step 6 重新提取。

### 配置加载

```bash
.venv/bin/python src/config.py
```
**预期**:打印 `top_n_per_category = 20, 4 lists, 15 rss, 12 subs`

---

## L3 — 端到端

### L3a 无 X、不 push(最快的端到端冒烟)

```bash
.venv/bin/python -m src.main --no-x --no-push
```

**预期流程**:
```
fetched total ~200 raw items
after dedup: ~195 items
ranking in 2 batches
ranked ~140 non-skip items
top counts: {'ai': 20, 'crypto': 20, 'tech': 20}
wrote slot HH:00 to daily/YYYY/MM/DD.md
dry-run: skipping git operations
```

**验证**:
- 看 `daily/YYYY/MM/DD.md` 是否生成
- 看里面是否有 `<!-- SLOTS_BEGIN -->` / `<!-- SLOTS_END -->` 标记
- 每类是否有 20 条(或少于 20 当内容不够时)
- 点开几条链接验证 url 有效

**耗时**:3-5 分钟(rank 占大头)

### L3b 完整(含 X、push)

```bash
.venv/bin/python -m src.main
```

**前提**:
- xreach cookie 就绪
- sources.yaml 的 4 个 list_id 已填
- git remote 可达

**预期**:
- 抓取总量 ~480(含 X 200+)
- 最终写入 daily/,git commit,push 到 origin
- GitHub 页面 `https://github.com/312362115/rss/blob/main/daily/YYYY/MM/DD.md` 可见渲染结果

### L3c 幂等验证

连续跑两次 L3a:
```bash
.venv/bin/python -m src.main --no-x --no-push
.venv/bin/python -m src.main --no-x --no-push
```

**预期**:第二次会看到 `slot HH:00 already in DD.md, skip write`,文件内容不变。

---

## launchd 回归

```bash
# 装载
./scripts/install_launchd.sh install

# 查看状态
./scripts/install_launchd.sh status
# 预期:launchctl list 里能看到 com.renlongyu.rss

# 查看日志(运行后)
./scripts/install_launchd.sh logs

# 卸载
./scripts/install_launchd.sh uninstall
```

---

## 故障排查速查

| 症状 | 可能原因 | 定位 |
|------|---------|------|
| `xreach auth check` 失败 | cookie 过期 | 重跑 `xreach auth extract --browser chrome` |
| X fetcher 返回 0 条 | list_id 是 TODO_ 占位 / list 为空 | 检查 sources.yaml |
| Reddit 返回 429 | UA 是默认值 / 同 IP 请求过多 | 确认 `meta.reddit_user_agent` 是描述性 UA |
| rank 全部走 fallback | `claude` CLI 不在 PATH / 超时 | `which claude` + 调大 `CLAUDE_TIMEOUT` |
| git push 失败 | remote 认证问题 / 分支落后 | 手动 `git pull --rebase` 后重跑 |
| MD 文件时段顺序错 | insert_slot_into_file bug | `pytest tests/test_render.py -k insert` |
| launchd 不触发 | plist 未 load / Mac 睡眠 | `launchctl list | grep rss` 确认 |

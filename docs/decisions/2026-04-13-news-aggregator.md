# 复盘:每日新闻聚合器 — 2026-04-13

## 需求概述

- **目标**:本地每 4h 自动抓取 AI/币圈/科技圈(X + HN + Reddit + RSS),LLM 分类 + 打分,生成中文日报 MD,`git push` 到 private 仓库
- **结果**:完整闭环跑通,首日发布 2 个 slot(08:00 + 14:00),launchd 定时装载,18:00 会自动触发第三个 slot
- **过程顺利度**:⭐⭐⭐ (3/5)——方向改过 4 次、踩过 3 个真实坑,但最终稳了

## 做得好的(保持)

### 1. 数据源调研扎实,避免了一个坑方向

开 spec 前先验证 2026-04 的 X 抓取现状:
- 查了 RSSHub / twscrape / xreach / nitter / 官方 API 五个方案
- 本地实测 `xreach --help` 可跑,`curl HN API` / `curl Reddit .json` 通
- **关键认知**:nitter 全挂、RSSHub twitter 路由间歇失效、x 官方 API 免费层 100 reads/月

这个调研让方案一开始就选对了主路径(xreach),避免了写完 RSSHub Docker 才发现 cookie 过期频繁的弯路。

### 2. 核心依赖"先验证再设计"

写 spec 前,先 `npm install -g xreach-cli` + `xreach --help` 确认命令能跑,再把参数写进 spec。这避免了"设计好了发现工具根本不是这样"的返工——类似的教训是 xreach 字段 camelCase 问题(见下)。

### 3. 反 scope creep:多次砍功能

spec 最初设计了一堆复杂特性,在方案评审和试跑中**主动砍掉**了:

| 砍掉的功能 | 理由 |
|---------|------|
| 双仓(脚本 private + 结果 public + Pages) | 单 private 仓 GitHub 网页原生渲染 MD 够了 |
| Jekyll just-the-docs 静态站 | 过度设计,GitHub MD 渲染免费 |
| 当日汇总重排(23:00 生成 Top 20 摘要) | 4h slot 本身就是"新鲜热度",不需要再聚合 |
| SQLite 跨时段去重 | 每个 slot 独立,重复出现本身就是"重要"信号 |
| 后来又加回来"slot 内 URL 去重" | 跨时段是噪音,slot 内同一 URL 多源命中该合并 |

最终版本非常扁平:`fetch → dedup → rank → render → publish`,5 步线性。

### 4. 小步 commit,每个都能独立 review

10 个 commit,每个 scope 清晰:`scaffold → fetch → rank+render → publish+main+launchd → fix(x) → daily → refactor(render+rank) → daily → schedule → lint`。出问题可以随时 revert 一个 commit,不会牵连其他。

### 5. 53 个单元测试 + 4 个活水 smoke test

所有模块都有单元测试(dedup 13 / rank 15 / render 11 / x_fetcher 9 / publish 7),每个 fetcher 还有 `if __name__ == "__main__":` 的活水 smoke,手动一行命令就能验证真实接口通。改动后一分钟 pytest 全量回归。

---

## 做得不够好的(优化)

### 1. 第一轮 spec 过度设计,写完 90% 后才开始砍

**现象**:我按"完整功能"写了约 700 行 spec,包含双仓、Pages、Jekyll 主题、当日汇总、SQLite 去重等。用户在评审阶段**分 4 次砍掉**了所有这些复杂度。

**原因**:我预设"用户想要完整生产级系统",没有先问"最小可用版本是什么"。

**代价**:spec 三次大改(汇总→无汇总→倒序→独立文件 latest.md)、两次目录结构调整、plan 任务描述反复改。虽然没写代码所以不算返工,但消耗了用户的评审注意力。

**改进**:下次写 spec 前先问一句:**"这个需求最小可用版本(MVP)是什么?其他特性是不是 v0.2 再加?"** 这个问题会强制把 spec 从"完整方案"降到"第一版闭环"。

### 2. 用 API 文档推测 xreach 的 JSON 格式,实际完全不对

**现象**:我按 Twitter v1 API 的 `id_str` / `full_text` / `created_at` / `favorite_count` 写 parse_tweet,测试 fixture 也是这些字段。实际 xreach 0.3 输出的是 **camelCase**:`id` / `text` / `createdAt` / `likeCount`。直到真实跑 `xreach tweets sama` 看输出才发现。

**原因**:跳过了"拿真实响应当 fixture"这一步,凭对 Twitter API 的印象写代码。

**代价**:写完 8 个 mock 单元测试 + 集成完才发现字段错,重写 parse_tweet + 测试 fixture。所幸测试都 mock 了 subprocess,改 fixture 的成本不高。

**改进**:下次集成第三方 CLI/API,**第一件事**是手动跑一次真实命令,保存一份输出样本作为 fixture,代码根据 fixture 来写。而不是看 API 文档或源代码推测。

### 3. Claude CLI 批处理 100 条时不稳定,第一次 push 质量差

**现象**:第一次完整 run(08:00 slot)batch 100 × 5 批。batch 1 正常 2 min,batch 2 **突然卡 32 min**,batch 3 超时(300s),batch 4 直接 error,走了 fallback。结果 AI 类 20 条里 9 条带 `[LLM 降级]` 前缀的英文原标题,用户看到排版很乱。

**原因**:没想过 Claude CLI 订阅模式会对连续大 prompt 触发 rate limit / 冷却,原本以为 100 条 × 5 批能稳跑。

**代价**:一次 push 了质量差的日报(d307348),然后才改代码。虽然覆盖很快,但用户看到过污染版本。

**改进**:下次做 LLM 批处理时:
1. **保守起步**:先 20-30 条/批,有监控数据再加
2. **批间 sleep 15s+**(rate limit 保护)
3. **retry 1 次后再 fallback**(LLM 偶发抖动很常见)
4. **fallback 要优雅**:空 comment + importance 降权,让 fallback 条目自然排到榜尾,而不是带污染 prefix

这些改进在 v0.1 第二次 run(14:00 slot)完全生效——11 批全部成功,retry 触发 3 次全部 retry 后成功,零 fallback 污染。

### 4. Chrome cookie 第一次提取失败,浪费了 10 分钟定位

**现象**:`xreach auth extract --browser chrome` 第一次返回 "Could not find required X/Twitter cookies",哪怕用户说"chrome 好了"。实际上是 Chrome 里有两个 Google 账号,小号登录的 x.com 在**另一个 Google profile** 下(虽然 Chrome 在本地只有一个 "Default" profile 目录)。

**原因**:Chrome 的 "本地 profile" 和 "Google 账号 profile" 是两回事。同一个本地 profile 可以来回切 Google 账号,cookie 也跟着切。当时我直接 sqlite 查了 Default/Cookies 发现零条 x.com cookie,才意识到用户登的 Google 账号是另一个。

**代价**:排错 + 重新切账号 ~10 分钟。

**改进**:下次遇到"浏览器 cookie 提取失败",**第一个诊断步骤**是直接查 sqlite3 cookie DB 看域名是否真的有对应 cookie,而不是先怀疑 Chrome 是否在运行、profile 是否对等 UI 层面的问题。

---

## 通用能力沉淀

### 跨项目可复用的经验

1. **LLM 批处理参数的"安全区间"**:50 条/批 + 15s 间隔 + retry 1 次 + timeout 600s,这套参数在 Claude CLI 订阅模式下稳定,100 条/批会抖动。

2. **xreach-cli 的 3 个坑**:
   - 字段是 camelCase(`id` / `text` / `createdAt` / `likeCount`),不是 v1 API 的 snake_case
   - `-n` 是"每页",默认会翻页,必须 `--max-pages 1` 才能限制
   - cookie 从 Chrome 提取时,同一本地 profile 下可能有多个 Google 账号,登错号直接失败

3. **X list 的结构价值**:60 个 KOL 分 4 个 list → 4 次请求就搞定,比逐个 user 抓省 15 倍请求量,且 list 的"合并时间线"天然按时间倒序返回。

4. **Spec 过度设计的反模式**:不问 MVP 就写完整方案 → 评审阶段被砍 4 次。下次先问"最小闭环是什么"。

### 本项目的已知 v0.2 方向(不阻塞当前 done)

- [ ] 3 个挂掉的 RSS feed 换源或移除(Anthropic / HF Daily Papers / Bankless)
- [ ] xreach cookie 失效自动检测 + 告警(现在要手动 `auth check`)
- [ ] 仓库是否改 public(user 已问,待验证 4 个 X list 都是 Private 后可改)
- [ ] 所有 slot 一天总量 ~180 条可能偏多,观察用户阅读习惯后决定是否下调 `top_n_per_category`

---

## 行动项

- [x] v0.1 代码落地、测试覆盖、launchd 装载完成
- [x] 首次生产运行 14:00 slot push 成功(commit `125ce28`)
- [x] 将 3 条关键经验写入 memory(LLM 批处理参数 / xreach 字段 / spec MVP 反模式)
- [ ] 2026-04-14 18:00 第一次自动触发后,验证 launchd 生产运行的稳定性
- [ ] 1-2 周后根据实际日报质量决定是否改 public 仓

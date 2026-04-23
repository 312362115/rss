# Backlog Index

## P0 — 紧急
<!-- 当前无 P0 -->

## P1 — 重要
- [ ] [外部抓取三路径方法论 + Anthropic/HF 接入](2026-04-23-web-fetcher-routing.md) — 沉淀 A/B/C 路径决策树,MVP 落地路径 B(Jina Reader),修复 Anthropic/HF 失效源
- [ ] [扩展金融一手数据源 + finance-analysis skill 集成](2026-04-20-finance-sources-expansion.md) — 新增 SEC/HKEX/IR/FRED/arXiv 金融源,日报加"金融"区块,对接 .claude 的 finance-analysis skill 做 Alpha 发现
- [x] [每日新闻聚合器](2026-04-13-news-aggregator.md) — 本地定时抓取 AI/币圈/科技圈新闻,LLM 分类打分,写 daily/ + git push(单 private 仓,无 Pages)

## P2 — 普通
- [ ] [按领域抓取(路径 C)接入 Exa](2026-04-23-exa-topic-fetcher.md) — 按话题/关键词搜索的未实现路径,候选工具 Exa / SerpAPI
- [x] [抓取频率分层](2026-04-14-schedule-layering.md) — X 小时更 + HN/Reddit/RSS/GitHub Trending 日更,顺带修 X 分页超 cap + 新增 GitHub Trending 源

## P3 — 低优
<!-- 当前无 P3 -->

---
priority: P2
status: open
---

# 按领域/话题抓取(路径 C)- 接入 Exa

## 背景

外部内容抓取路径方法论中(`docs/specs/2026-04-23-external-source-routing-design.md`),**路径 C 是按话题/关键词搜索**,当前未实现。

## 典型需求

- "AI coding 赛道"最新产品发布(不局限某几个 URL)
- "crypto L2"新币发行
- "机器人 / AGI"相关学术突破
- 任何"按话题而非固定源"的信号采集

## 候选工具

| 工具 | 费用 | 说明 |
|---|---|---|
| [Exa](https://exa.ai) | 免费额度 + 按量 | AI 语义搜索,支持 recency / domain filter |
| SerpAPI | 付费 | Google 搜索结果 |
| Google Alerts | 免费 | 关键词订阅 → 邮件 → 需转 RSS |

Exa 在 Agent-Reach 里被推荐,免 Key(MCP 模式),首选。

## MVP 落地草图

1. `sources.yaml` 新增 `exa` 段:
   ```yaml
   exa:
     ai:
       - {query: "AI coding agent new product launch", recency: day, limit: 10}
       - {query: "open source LLM release", recency: day, limit: 10}
     crypto:
       - {query: "L2 token launch", recency: day, limit: 10}
   ```
2. `src/fetch/exa_fetcher.py` — 调用 Exa API(或 MCP),按 query 拿结果,映射到 `Item`
3. `main.py::build_daily_fetchers` 注册 ExaFetcher

## 触发条件

- 当前 5 条 feed 类别固定(AI/Crypto/Tech),用户表达出"某个垂直赛道想跟进"的需求时启动
- 或扩展到金融领域(对接已规划的 `finance-analysis` skill)时同步做

---
priority: P1
status: in-progress
spec: docs/specs/2026-04-23-external-source-routing-design.md
tests: docs/tests/web-fetcher.md
---

# 外部内容抓取路径化 + Anthropic/HF 接入(路径 B)

## 背景

2026-04-23 晨间 run 发现 4 个 RSS 源挂掉:
- Anthropic / HF Daily Papers — 官网改版取消 RSS(永久)
- Bankless — 自建域名证书错 + Substack 邀请制
- Simon Willison — 偶发 SSL(无需处理)

同时用户指出:项目现有 `xreach-cli` 抓 X 的模式本就是 "CLI + Cookie 绕过反爬",但这套路径没系统化记录,导致遇到新型源失效时反复"一事一议"。

## 目标

1. **方法论沉淀**:外部内容抓取归纳为 3 条路径(A: CLI+Cookie / B: Jina Reader / C: 按领域搜索),写 spec 作为后续新渠道的决策基准
2. **修复当前失效源**:Anthropic / HF 走路径 B 接回,Bankless 移除
3. **接口预留**:`WebFetcher` 设计为 parser 注册表模式,新增源只需 yaml 加行 + 必要时加 parser 函数

## 本次交付范围(路径 B)

- [x] `docs/specs/2026-04-23-external-source-routing-design.md` — 方法论 + 决策树
- [x] `src/fetch/web_fetcher.py` — Jina Reader + 3 parser(anthropic_news / hf_papers / generic_markdown)
- [x] `sources.yaml` — 新增 `web` 段,删除失效 RSS,Bankless 移除
- [x] `src/main.py` + `config.py` — 注册 WebFetcher
- [x] `src/fetch/base.py` — `Source` 增加 `"web"`
- [x] `docs/tests/web-fetcher.md` — 回归用例
- [ ] 端到端 smoke test 通过

## 未来扩展(不在本次范围)

**路径 A(CLI + Cookie)** 还未形式化,当前只有 X;未来接入时参考:
- Reddit 深度抓取(rdt-cli,拿完整 thread+评论)
- YouTube / B 站字幕(yt-dlp)
- 小红书(xhs-cli)

**路径 C(按领域搜索)** 未实现,典型需求:
- "AI coding 新产品" 按话题抓
- "某 L2 新币" 按赛道抓
- 候选工具:Exa API(AI 语义搜索,有免费额度)/ SerpAPI / Google Alerts

延伸开一个 follow-up backlog:`按领域抓取(路径 C)接入 Exa`。

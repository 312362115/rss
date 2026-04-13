---
priority: P1
status: in-progress
spec: docs/specs/2026-04-13-news-aggregator-design.md
plan: docs/plans/2026-04-13-news-aggregator-plan.md
---

# 每日新闻聚合器

## 需求

本地定时(每 4 小时)抓取 AI / 币圈 / 科技圈新闻,经 LLM 打分筛选后生成**中文分类日报 Markdown**,落盘到**同仓** `daily/` 目录,`git push` 到 private 仓库,靠 GitHub 网页原生 MD 渲染查看。

## 动机

- 目前依赖手动刷 X/Reddit/HN 才能跟上圈内一手消息,效率低且有遗漏
- 想要一个"打开 GitHub 点一下就能看完最重要新闻"的个人情报室
- 数据源以**海外社交媒体(X 为核心)+ 聚合站**为主,一手消息最快

## 验收标准

1. X 抓取跑通(通过 `xreach` + 小号 cookie)
2. 非 X 数据源(HN / Reddit / RSS)全部跑通
3. 每 4 小时 launchd 自动触发一次,失败不补跑(可接受)
4. 产出 `daily/YYYY/MM/DD.md`,按 4h 时段分节(**倒序,新的在顶**),每节分 AI / 币圈 / 科技 三类榜单
5. `git push` 后 GitHub 网页可见渲染后的 MD
6. 端到端手动跑一次全流程并验证输出

## 关联

- Spec: `docs/specs/2026-04-13-news-aggregator-design.md`
- Plan: `docs/plans/2026-04-13-news-aggregator-plan.md`

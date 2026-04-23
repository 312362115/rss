# web_fetcher 回归用例

> 模块: `src/fetch/web_fetcher.py`
> 路径: B(Jina Reader)
> 方案: `docs/specs/2026-04-23-external-source-routing-design.md`

## 用例 1:Anthropic News 解析

- **前置条件**: 网络可访问 `r.jina.ai`,`sources.yaml` 里 `web.ai` 含 Anthropic News 条目
- **执行命令**: `.venv/bin/python -m src.fetch.web_fetcher`
- **预期结果**:
  - 日志 `Web Anthropic News: parsed N items via anthropic_news`,N ≥ 5
  - 输出条目的 URL 都以 `https://www.anthropic.com/` 开头
  - 标题不含 "Product " / "Announcements " 等类别前缀(已剥离)
  - `normalized_score` 按顺序递减(从 30.0 开始)

## 用例 2:HF Daily Papers 解析

- **前置条件**: 同上
- **执行命令**: 同上
- **预期结果**:
  - 日志 `Web HF Daily Papers: parsed N items via hf_papers`,N ≥ 3
  - 输出条目 URL 都是 `https://huggingface.co/papers/<arxiv_id>` 格式(形如 `2604.19859`)
  - 每条 ID = arxiv_id,去重后无重复

## 用例 3:Jina Reader 故障降级

- **前置条件**: 把 `JINA_READER_BASE` 改为 `https://invalid.example.com/`(仅本地测试改)
- **执行命令**: 同上
- **预期结果**:
  - 日志出现 `Web <feed>: fetch failed: ...` WARNING
  - 进程不抛异常,返回空列表,下游流程不受影响

## 用例 4:未知 parser

- **前置条件**: `sources.yaml` 某条目 `parser: nonexistent`
- **预期结果**: 日志 `Web <feed>: unknown parser: nonexistent`,返回空

## 用例 5:generic_markdown 兜底

- **前置条件**: `sources.yaml` 新增任意支持 Jina Reader 的 URL,不指定 parser(或指定 `generic_markdown`)
- **预期结果**: 能返回页面中标题 ≥ 10 字符的所有 Markdown 链接(用于新源冒烟验证)

## 用例 6:端到端集成(daily 流程)

- **前置条件**: launchd 调度或手动触发
- **执行命令**: `.venv/bin/python -m src.main --daily-only --force-daily --no-push`
- **预期结果**:
  - 日志包含 `[web] returned N items` (N ≥ 10)
  - 日志 `daily fetched ... raw items` 总数包含 web 的贡献
  - 最终写入 `daily/YYYY/MM/DD.md` 的 AI 段落中含 Anthropic / HF Papers 条目

## 回归触发时机

- 新增 `web.*` 源后
- 修改 parser 正则后
- Jina Reader 服务迁移或改 schema 后(如 404 / 403 开始出现)
- Anthropic / HF 官网改版后(条目数骤减或为 0 时)

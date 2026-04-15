# 抓取频率分层 — 开发计划

## 关联
- 方案: `docs/specs/2026-04-15-schedule-layering-design.md`
- backlog: `docs/backlog/2026-04-14-schedule-layering.md`

## 子任务

- [x] 1. sources.yaml 加 schedule 字段 + GitHub Trending 配置
  - 做什么: 4 个源加 `schedule`,新增 `github_trending` 段,`hotness_caps` 加 `github_star_delta`
  - 涉及: `sources.yaml`, `src/config.py`(可能需要扩字段)
  - 验收: `python -m src.config` dump 出来字段都在

- [x] 2. base.py: 扩 Source literal 和 SOURCE_PRIORITY
  - 做什么: 加 `"github"` 到 Source、SOURCE_PRIORITY
  - 涉及: `src/fetch/base.py`
  - 验收: import 不报错,type checker 通过

- [x] 3. GitHub Trending Fetcher
  - 做什么: 新建 `github_fetcher.py`,抓 trending HTML,解析 owner/repo/desc/star_delta,产出 Item
  - 涉及: `src/fetch/github_fetcher.py`(新建)
  - 验收: 单跑 `python -m src.fetch.github_fetcher` 输出 ≥10 条且字段齐全

- [x] 4. X 跨 slot 去重(.cache/x_seen.json)
  - 做什么: 新增 `src/dedup.py::filter_x_seen()` + `prune_x_seen()`,X fetcher 调用前过滤
  - 涉及: `src/dedup.py`, `src/main.py`(挂到 X 后处理), `.gitignore`
  - 验收: 连跑 2 次,第 2 次 X 条目数 ≈ 0(假设无新推);.gitignore 含 `.cache/`

- [x] 5. X 分页超 cap 修复
  - 做什么: 排查 xreach 调用,确认 limit 不生效后在 fetcher 内硬截断 `[:tweets_per_run]`
  - 涉及: `src/fetch/x_fetcher.py`
  - 验收: tweets_per_run=50 时实抓 ≤50

- [x] 6. render.py: DAILY marker + render_daily_section + render_x_slice_file
  - 做什么: 新增 `DAILY_BEGIN/DAILY_END` 常量、`render_daily_section(groups, gh_items)`、`render_x_slice_file(d, slot, groups)`
  - 涉及: `src/render.py`, `src/templates/daily.md.j2`(新建), `src/templates/x_slice.md.j2`(新建)
  - 验收: `__main__` 用假数据渲染输出符合预期格式

- [x] 7. publish.py: 拆文件写入 + 索引刷新
  - 做什么: 新增 `daily_index_path()`, `x_slice_path()`, `write_x_slice()`, `write_daily_section()`, `refresh_x_links_in_index()`, `daily_section_exists()`
  - 涉及: `src/publish.py`
  - 验收: 单跑写出 `daily/2026/04/15.md` + `daily/2026/04/15/10.md`,索引顶部 X 链接行正确

- [x] 8. main.py: 调度逻辑改造(hourly + daily 自愈)
  - 做什么: `build_fetchers(schedule=...)` 按字段过滤,`run()` 拆 hourly/daily 两段,daily 段判断 marker 自愈补跑
  - 涉及: `src/main.py`
  - 验收: 同一天连跑 2 次,第 2 次 daily 段被跳过;手动删 marker 后 daily 段重新执行

- [x] 9. 端到端联调 + 回归测试沉淀
  - 做什么: `--no-push` 跑完整流程,验证两类文件落地、git 提交干净、跨 slot 去重生效
  - 涉及: `docs/tests/schedule-layering.md`(新建,记录回归命令)
  - 验收: 测试用例文档中含可执行命令,跑过一遍全部通过

- [x] 10. 文档同步
  - 做什么: 更新 `docs/specs/2026-04-13-news-aggregator-design.md` 频率描述、`README.md` 描述新结构、关闭 backlog `2026-04-14-schedule-layering.md` 状态
  - 涉及: 上述文件 + `docs/backlog/INDEX.md`
  - 验收: backlog INDEX 标 `[x]`,spec 中频率章节准确

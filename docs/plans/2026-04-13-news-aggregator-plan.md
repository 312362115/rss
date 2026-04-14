# 每日新闻聚合器 — 开发计划

## 关联

- Spec: `docs/specs/2026-04-13-news-aggregator-design.md`
- Backlog: `docs/backlog/2026-04-13-news-aggregator.md`

## 里程碑

```
M1 骨架 & 配置   →   M2 采集层   →   M3 打分渲染   →   M4 发布 & 定时   →   M5 端到端联调
```

---

## 子任务

- [x] 0. 技术调研 & spec
  - 做什么:X 抓取现状调研、xreach 可用性验证、HN/Reddit 连通性测试、spec 写作
  - 交付:`docs/specs/2026-04-13-news-aggregator-design.md`
  - 验收:方案包含背景/调研/决策/技术方案/风险,已通过 User Review(待)

### M1 骨架 & 配置

- [x] 1. 项目脚手架 — 完成
  - 交付:`pyproject.toml` / `.gitignore` / `README.md` / `src/__init__.py` / `src/config.py` / `src/fetch/__init__.py` / `sources.yaml` / `daily/.gitkeep`
  - 验收:`.venv/bin/python src/config.py` 输出 `top_n_per_category=20, 4 lists, 15 rss, 12 subs`

- [x] 2. 小号准备 Runbook — 完成
  - 交付:`docs/runbooks/x-account-setup.md`,9 步完整 SOP(注册 → 养号 → 建 list → 装 xreach → 导 cookie → 填 sources.yaml)
  - 用户离线执行,不阻塞 M2 其他任务开发(只阻塞 X fetcher 的集成测试)

### M2 采集层

- [x] 3. Fetcher 基类 & 数据模型 — 完成
  - 交付:`src/fetch/base.py`(Item + Fetcher ABC + SOURCE_PRIORITY)、`src/dedup.py`(normalize_url + url_hash + dedup_in_slot)、`tests/test_dedup.py`(13 tests)
  - 验收:`.venv/bin/pytest tests/test_dedup.py` → 13 passed

- [x] 4. HN Fetcher — 完成
  - 交付:`src/fetch/hn_fetcher.py`,Firebase API 集成,`_normalize` 热度计算
  - 验收:`python -m src.fetch.hn_fetcher` 真实返回 13 条 (score 156-565,normalized 9.4-30.0)

- [x] 5. Reddit Fetcher — 完成
  - 交付:`src/fetch/reddit_fetcher.py`,描述性 UA,支持 self post 和外链
  - 验收:`python -m src.fetch.reddit_fetcher` 真实返回 25 条(3 个 sub)

- [x] 6. RSS Fetcher — 完成
  - 交付:`src/fetch/rss_fetcher.py`,feedparser 解析,bozo 容错,HTML 标签剥离,支持 `ua_override`
  - 验收:`python -m src.fetch.rss_fetcher` 真实返回 20 条(3 个 feed,Anthropic 因 XML 问题被跳过)
  - 已知问题:`https://www.anthropic.com/news/rss.xml` 返回非良构 XML,需要后续换源

- [x] 7. X Fetcher(xreach 封装)— 代码完成,集成测试待 M4 后小号就绪
  - 交付:`src/fetch/x_fetcher.py`(subprocess 调 xreach list-tweets / tweets,jsonl 解析)、`tests/test_x_fetcher.py`(8 tests,mock subprocess)
  - 验收(单元):`.venv/bin/pytest tests/test_x_fetcher.py` → 8 passed
  - 验收(集成):待 cookie 就绪后 `python -m src.fetch.x_fetcher` 真实调用

- [ ] 8. 单次 slot 内跨源 URL 去重(in-memory)
  - 做什么:
    - 实现 `normalize_url` + `url_hash`(spec §5.4.2a)
    - 实现 `dedup_in_slot(items)`:单次 slot 内按 `url_hash` 去重,同一 URL 多源命中时按 `SOURCE_PRIORITY` (X > HN > Reddit > RSS) 保留优先级最高的那条
    - **无 SQLite**,纯内存,每次运行独立
  - 涉及:`src/fetch/base.py`(加 url_hash 字段)、`src/dedup.py`(normalize_url + dedup_in_slot)、`tests/test_dedup.py`
  - 验收:
    - 输入:两条 URL 规范化后相同但 source 不同(HN + Reddit 同一 TechCrunch 文章),只保留 HN 版本
    - 输入:带 `utm_*` 参数和不带的同一 URL,被识别为同一条
    - 输入:URL 完全不同的条目,全部保留

### M3 打分渲染

- [x] 9. Claude CLI 打分 rank — 完成
  - 交付:`src/rank.py`、`prompts/classify.md`、`tests/test_rank.py`(14 tests)
  - 功能:批 100 条送 Claude CLI、markdown 代码块剥离、id 对齐、skip 过滤、LLM 漏条走 fallback、整体失效走关键词启发式分类
  - 验收(单元):14 tests 全过
  - 验收(集成):待 main.py 串联后一并测

- [x] 10. 模板 & 渲染 render — 完成
  - 交付:`src/render.py`、`src/templates/slot.md.j2`、`tests/test_render.py`(9 tests)
  - 功能:`render_skeleton` 骨架、`render_slot_section` 三分类 + 空状态、`insert_slot_into_file` 倒序插入 + 幂等、`current_slot_label` 4h 对齐
  - 验收:9 tests 全过,冒烟输出 MD 肉眼检查 OK

### M4 发布 & 定时

- [ ] 11. 脚本仓 git 初始化 + `daily/` 目录
  - 做什么:
    - `git init` + `git remote add origin git@github.com:312362115/rss.git`
    - 写 `.gitignore`(忽略 `.venv/ .secrets/ __pycache__/ *.pyc`)
    - 创建空 `daily/` 目录(加 `.gitkeep`)
    - 首个 commit:骨架 + spec/plan/backlog
    - `git push -u origin main`
  - 涉及:`.gitignore`、`daily/.gitkeep`
  - 验收:GitHub 上能看到仓库有初始 commit,private 可见

- [ ] 12. 发布 publish
  - 做什么:
    - `publish(slot_md, date, slot)`:首次创建则写 skeleton,否则读文件
    - 幂等检查:若 `## HH:00 时段` 已存在则跳过
    - 将新时段节插入到 `<!-- SLOTS_BEGIN -->` 的下一行(倒序,最新在顶)
    - git pull --rebase → add → commit → push
  - 涉及:`src/publish.py`,`tests/test_publish.py`(git 操作 mock)
  - 验收:
    - 单元测试:首次创建 / 插入第二个时段(新时段在上)/ 重复相同时段(跳过)三个场景
    - 集成:手动连续跑两次,第二次因幂等跳过;修改时间到下个 slot 再跑,新时段正确插到顶部

- [ ] 13. 主入口 main
  - 做什么:
    - 流程:fetch(并行四源)→ `dedup_in_slot` → rank(Claude CLI 分批 100) → 每类 Top 20 → render → publish
    - 全程日志 + 异常兜底(单源失败不中断整体)
    - 根据当前时间自动计算 slot 标签(00/04/08/12/16/20)
  - 涉及:`src/main.py`
  - 验收:`python src/main.py` 端到端跑通一次

- [ ] 14. launchd 定时
  - 做什么:
    - 写 `launchd/com.renlongyu.rss.plist`:每 4h(00/04/08/12/16/20)跑 `main.py`
    - 提供 `scripts/install_launchd.sh` 一键 `launchctl load`
  - 涉及:`launchd/com.renlongyu.rss.plist`、`scripts/install_launchd.sh`
  - 验收:`launchctl list | grep rss` 能看到,日志正常输出

### M5 端到端联调 & 回归测试

- [ ] 15. 回归测试用例
  - 做什么:把开发中写的所有验证脚本整理为 `docs/tests/news-aggregator-e2e.md`,可重复执行
  - 涉及:`docs/tests/news-aggregator-e2e.md`
  - 验收:按文档命令可全量回归(HN / Reddit / RSS 各一条 smoke test + X cookie check + 一次完整跑)

- [ ] 16. 端到端验收
  - 做什么:按 spec 附录 B 的步骤手动完整跑一次,确认 M1-M5 所有交付物都工作
  - 验收:
    - 一次完整运行输出 `daily/2026/04/13.md`,时段节齐全
    - `git push` 成功后 GitHub 网页可见渲染后的 MD
    - launchd 下一个周期自动触发并出现第二个时段(插入到已有时段的上方)
  - 交付:运行截图 / GitHub 页面链接

### 后续(不阻塞 v0.1 关闭)

- [ ] 17. task-finish 自检 + 复盘沉淀
  - 做什么:调 `task-finish` skill 做 CR 自检,把踩坑和决策写入 `docs/decisions/`
  - 涉及:`docs/decisions/2026-04-13-news-aggregator.md`

---

## 关键依赖和阻塞

| 任务 | 阻塞条件 |
|------|---------|
| 7(X Fetcher 集成测试) | 依赖任务 2 完成(小号就绪 + cookie) |
| 14(launchd) | 依赖任务 13 完成 |
| 16(端到端) | 依赖前面所有任务 |

## 开放问题

无(已全部确认:单仓 private,remote `git@github.com:312362115/rss.git`,无 Pages,无去重,无汇总)。

---

## 估时

| 里程碑 | 估时(专注开发) |
|-------|---------------|
| M1 骨架 | 0.5 天 |
| M2 采集层 | 1-1.5 天(X fetcher 集成有调通摩擦) |
| M3 打分渲染 | 0.5 天 |
| M4 发布定时 | 0.5 天 |
| M5 端到端 | 0.5 天 |
| **合计** | **3-3.5 天** |

额外依赖(不计入估时,用户侧):
- X 小号养号 3-7 天
- cookie 提取 & list 创建:~30 分钟

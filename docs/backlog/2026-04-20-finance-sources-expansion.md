---
priority: P1
status: open
spec: docs/specs/2026-04-20-finance-sources-integration.md
plan:
---

# 扩展金融一手数据源 + 对接 finance-analysis skill

## 背景

**2026-04-20 触发**：在 `.claude` 仓库新建了 `skills/finance-analysis` skill，覆盖 HK IPO 打新 + AI 主题投资 framework，核心方法论是"**Alpha 在执行不在发现**"——明牌信号所有人都看得到，真正赚钱靠"识别趋势启动"的日频/周频巡检。

当前 rss-daily 仓库已覆盖 **AI / 币圈 / 科技** 三大类新闻源，但**金融投资决策需要的信源基本缺失**：
- 监管披露（SEC EDGAR / HKEXnews / 巨潮）
- 大厂 IR 一手公告（NVDA / Meta / MSFT / TSLA / CEG 等）
- 央行 / 经济数据（FRED / BLS / BEA）
- 中国 A 股公告（巨潮 / 证监会）
- arXiv 论文（虽有 HF Daily Papers 但范围较窄）

这些源**完全免费 + RSS 可达 + 价值极高**，补上这块，rss-daily 就从"科技新闻聚合器"升级为"个人 Alpha 发现扫描器"。

## 核心判断：RSS + Framework = 自动化 Alpha 扫描

三层结合：
- **RSS 仓库**（当前）：抓取 + 预筛选 + 落盘 `daily/YYYY/MM/DD.md`
- **finance-analysis skill**（`.claude/skills/`）：判断规则 + 趋势启动识别 + 决策卡
- **人**：读 daily brief，按 skill 月度巡检 checklist 决策

RSS 补数据，skill 补方法，结合产生"日频 Alpha 发现系统"。

## 目标

1. 扩展数据源到**金融领域 P0 清单**（完全免费 + 高 Alpha 价值）
2. 在 `sources.yaml` 加一个新类别 `finance`（与 ai / crypto / tech 平级）
3. 通过 `daily/` 文件作为契约，被 `finance-analysis` skill 读取消费
4. 不在 rss 仓库做"决策逻辑"——只负责**抓取 + 预筛选**，决策留给 skill

## 非目标

- ❌ 本次**不做**卖方研报抓取（付费/反爬复杂，留 P2）
- ❌ 本次**不做**年报全文解析（100+ 页，需要专门 LLM pipeline，留后续 plan）
- ❌ 本次**不做**决策引擎（skill 负责，rss 只抓取）
- ❌ 本次**不做**警报推送（先手动每日 review）

## 源清单（P0 优先）

### P0 - 立刻扩（免费 + 价值最高）

#### 年报/季报/披露（filings）
- **SEC EDGAR**（10-K/10-Q/8-K/DEF 14A/13F）— 官方 RSS
- **HKEXnews**（港股公告）— 官方 RSS
- **巨潮资讯网**（A 股公告）— 部分 RSS + 爬虫

#### 大公司 IR（ir）
- 美股：NVDA / Meta / MSFT / GOOGL / TSLA / AMD / TSMC / Micron / CEG / VST
- 中概 / 港股：Tencent (00700) / Alibaba (BABA/9988) / JD / Baidu

#### 大公司技术突破（bigtech-research）
**美国大厂**：NVIDIA Blog / Google AI / Google Research / Meta AI / Meta Engineering / MS Research / Apple ML / Amazon Science
**中国大模型独立公司**：DeepSeek / Zhipu / Moonshot / MiniMax / Baichuan / 01.AI
**中国互联网大厂 AI**：
- 字节：Seed / 火山引擎开发者 / Bytedance HF 组织
- 阿里：Qwen GitHub + HF / 阿里云开发者 / 达摩院
- 腾讯：Hunyuan HF / 腾讯云开发者 / Tencent AI Lab
- 华为：昇腾 / 华为开发者
- 百度：ERNIE HF / AI 开发者

**中国大厂 RSS 兜底策略**：中文源多走微信公众号，标准 RSS 不完整。
1. 优先走**官方 RSS**（验证可用）
2. 退而求其次**追踪 HuggingFace 组织动态**（bytedance-research / Qwen / tencent / baidu 都有 HF 组织，API 稳定）
3. 再退**追踪 GitHub releases**（Qwen / DeepSeek 等开源项目）
4. 最后**RSSHub 代理微信公众号**（稳定性差但有总比没有强）

#### VC / 咨询行业分析（vc-reports）
- a16z / Sequoia / Bessemer / CB Insights / State of AI Report
- SemiAnalysis（半导体深度）/ Stratechery（战略）
- 中国：信通院白皮书 / 艾瑞咨询

#### 宏观数据（macro）
- **FRED** / BLS / Fed FOMC

#### 学术前沿（academic）
- **arXiv cs.LG + cs.CL + cs.RO**

#### 分析师评级（ratings）
- Benzinga Analyst Ratings（免费 RSS）

#### 产业脉搏（industry-pulse）
- TrendForce（存储/面板价格）/ CNCF / PitchBook

#### 开源技术发布（bigtech-research 补充）
- GitHub Releases: NVIDIA CUDA / vLLM / SGLang / Ollama / LangGraph / Transformers / DeepSeek-V3 / Qwen

### P1 - 可以扩（中等复杂度）

- 分析师评级变化（Finviz / Seeking Alpha / Benzinga RSS）
- Google Trends 关键词 YoY（通过 pytrends）
- 美联储 FOMC Minutes / Beige Book
- 中国央行 / 国家统计局 RSS（部分有）
- CCASS 南向持股日度变化（港交所）

### P2 - 高复杂度

- 东财研报 / 慧博投研（需爬虫 + 反爬）
- HBM 价格周报（TrendForce / DRAMeXchange，部分免费）
- 卫星 / 招聘数据（机构级，暂缓）

## 架构设计（核心契约）

```
【RSS 仓库职责】
  ↓ 抓取（扩 finance 类）
  ↓ 预筛选（blacklist 过滤 + 关键词匹配 + 去重）
  ↓ LLM 分类打分（复用现有 pipeline）
  ↓ 落盘 daily/YYYY/MM/DD.md
     └── 新增 "金融" 区块（含 finance.sec / finance.hkex / finance.a-shares / finance.ir / finance.macro / finance.academic）

【finance-analysis skill 职责】
  ↓ 用户主动调用（"今日 AI 有什么 Alpha 信号"）
  ↓ 读取最新 daily/*.md
  ↓ 匹配 watchlist（AI 产业链 8 层 + 打新 watchlist）
  ↓ 应用"趋势启动识别"三条判断
  ↓ 输出决策卡（按 skill templates/ 格式）
```

**不要**在 rss 仓库做决策（保持职责清晰）。

## 关键实施决策

1. **sources.yaml 新增 `finance` 类别**，与 ai/crypto/tech 平级
2. **schedule: daily**（金融披露大多日级更新，不需要 hourly）
3. **复用现有 LLM 分类打分 pipeline**，只需扩 prompt 加金融关键词
4. **日报模板新增"金融"区块**，与现有分区并列
5. **黑名单复用 finance-analysis 的 blacklist.yaml**（通过文件路径引用）

## 落地阶段

### 阶段 1：源清单 + 技术验证（1-2 天）
- [ ] 在 `sources.yaml` 新增 `finance` 顶层键
- [ ] 添加 P0 源（每类至少 2-3 个，验证 RSS 可抓取）
- [ ] 手动跑一次 `src.main --no-push`，检查金融类新闻是否进入日报
- [ ] 修复反爬 / UA / 编码问题

### 阶段 2：筛选与分类（1 周）
- [ ] LLM 打分 prompt 加金融关键词权重（AI 产业链 8 层 + 港股打新关键词）
- [ ] 日报模板新增"金融"区块（与 AI/币圈/科技并列）
- [ ] 回归测试：跑一周，看日报金融区块是否有价值

### 阶段 3：对接 finance-analysis skill（2 周）
- [ ] 在 skill 里新增 `references/integrations/rss-daily.md`，定义读取 daily/*.md 的契约
- [ ] skill 被调用时可选参数 `--rss-daily ~/workspace/rss/daily/`
- [ ] worked example：跑一次 "今日 Alpha 巡检"

### 阶段 4（可选，未来）：警报推送
- [ ] 评分 > 80 分的信号通过企业微信 / 邮件推送
- [ ] 月度 checkup 自动化 50%（skill 的 90 分钟人肉巡检压缩到 15 分钟）

## 验收标准

- **阶段 1 完成**：日报出现"金融"区块 ≥ 10 条一手信号/天
- **阶段 2 完成**：金融区块 Alpha 浓度明显高于普通新闻（主观评估）
- **阶段 3 完成**：skill 能读 daily 文件并产出决策卡 worked example
- **长期 KPI**：任何 AI 子赛道启动 3 个月内被识别（对齐 `ai-thematic-investing.md` 的 3 月 KPI）

## 参考

- finance-analysis skill：`~/.claude/skills/finance-analysis/`
- AI 主题 framework：`~/.claude/skills/finance-analysis/references/frameworks/ai-thematic-investing.md`
- 打新 framework：`~/.claude/skills/finance-analysis/references/frameworks/hk-ipo-arbitrage.md`
- 信源白名单：`~/.claude/skills/deep-research/references/sources/finance.yaml`
- 黑名单：`~/.claude/skills/deep-research/references/sources/blacklist.yaml`

## 备注

- 本 backlog 暂不启动，先记录完整方案。
- 待主 .claude 仓库 finance-analysis skill 稳定后（预计 2-3 周）再启动阶段 1。
- 优先级可能与 rss-daily 其他功能冲突，需要时重排。

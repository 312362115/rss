# 金融一手数据源扩展 + finance-analysis skill 集成方案

> 关联 backlog：`docs/backlog/2026-04-20-finance-sources-expansion.md`
> 关联外部：`~/.claude/skills/finance-analysis/`（主 Claude 仓库的金融分析 skill）

---

## 背景与动机

### 外部触发

2026-04-20 在主 `.claude` 仓库新建了 `finance-analysis` skill（0.1.0），覆盖：
- HK IPO 打新套利 framework（群核 0068.HK 实战沉淀）
- AI 主题投资 framework（8 层产业链 + 趋势启动识别系统）

核心方法论："**Alpha 在执行不在发现**"——明牌信号所有人都看得到，真正赚钱靠：
1. **精度差**（产业链推演 ≥ 2 跳）
2. **时点差**（苗头期识别，3 个月 KPI）
3. **仓位/持有/顶点识别差**

其中"**时点差**"需要**日频信号监控** —— 这是 rss-daily 的天然能力，但目前缺金融源。

### rss-daily 现状

| 类别 | 覆盖 | 质量 |
|------|------|------|
| AI | Anthropic / OpenAI / DeepMind / HF Papers / Simon Willison / MIT Tech Review | 优 |
| 币圈 | CoinDesk / The Block / Decrypt / Cointelegraph / Bankless | 优 |
| 科技 | TechCrunch / The Verge / Ars Technica / HN | 优 |
| **金融投资** | **空白** | 需补 |

### 核心判断

**三层结合 = 自动化 Alpha 发现扫描器**：

```flow
rss-daily 仓库 → 抓取 + 预筛选 + 落盘 daily/YYYY/MM/DD.md
↓
finance-analysis skill → 判断规则 + 趋势启动识别 + 决策卡
↓
人 → 每日 morning brief + 月度巡检 + 操作
```

---

## 现状分析

### 为什么现有 AI 源不够用来做投资决策

现有 AI 类源主要是：
- **技术前沿**（arXiv 通过 HF / Simon Willison）：知识价值高，但不直接指向个股
- **大厂官博**（Anthropic / OpenAI / DeepMind）：模型发布为主，不含产业链传导信号
- **科技媒体**（TechCrunch / Verge）：应用层为主

**缺失的维度**：
1. **财报/公告** —— Alpha 最集中的一手源
2. **大厂 Capex 指引** —— AI 产业链上游需求先行指标
3. **宏观数据** —— 成长股估值的锚
4. **港股/A 股公告** —— 中国 AI 链标的（CPO / 机器人 / 电力）
5. **分析师评级变化** —— 共识形成时点

### 不做的影响

如果不扩，rss-daily 继续是"科技新闻聚合器"，不是"投资决策支持系统"。finance-analysis skill 会变成"调用时临时 WebSearch"，无法发挥日频监控的价值。

---

## 调研与备选方案

### 方案 A：只扩 rss 源，保持 rss 仓库职责不变
- 在 `sources.yaml` 加 `finance` 类别
- rss 只抓取 + 预筛选 + 落盘，skill 负责判断
- ✅ 职责清晰，rss 可独立演进
- ✅ skill 可读 rss 输出，对接简单
- ❌ 仍需人工每天读日报

### 方案 B：rss + skill 深度耦合（决策链内置）
- rss 仓库直接集成决策逻辑
- 跑完抓取自动产出 Alpha 决策
- ❌ 职责混乱，rss 变成"金融工具"失去通用性
- ❌ 决策逻辑升级需改 rss 代码

### 方案 C：新建独立"金融扫描器"仓库
- 金融数据源 + 决策逻辑完全独立于 rss
- ❌ 重复造轮子（rss 已有抓取管道）
- ❌ 两套配置 / 两套运维

### 决策：方案 A

**核心理由**：
- **职责分离原则**：rss 抓数据，skill 做判断，人做决策
- **复用性**：rss 扩出来的金融源也可以给其他 skill 用（比如未来的 "risk-monitor"）
- **MVP 快**：先扩源 + 日报加区块，不需要改架构

**放弃**：方案 B 的"全自动决策"短期不实现，先人工每日 review（可以未来升级）。

---

## 技术方案

### 1. sources.yaml 扩展（5 个子类别）

**覆盖盘点与补齐**（相比初版 spec，补充了 big-tech / vc-research / 中国大模型官博 / 卖方评级）：

| 子类别 | 覆盖目的 | 价值 |
|-------|---------|-----|
| **finance.filings** | 年报/季报/重大事件（SEC/HKEX/巨潮） | ⭐⭐⭐⭐⭐ |
| **finance.ir** | 大厂 IR（Capex 指引 + 业绩电话会） | ⭐⭐⭐⭐⭐ |
| **finance.bigtech-research** | 大公司技术突破（NVDA/Meta/Google 研究博客 + 中国大模型官博） | ⭐⭐⭐⭐⭐ |
| **finance.vc-reports** | VC / 咨询行业分析（a16z/Sequoia/信通院/State of AI） | ⭐⭐⭐⭐ |
| **finance.macro** | 宏观数据（FRED） | ⭐⭐⭐⭐ |
| **finance.academic** | 学术前沿（arXiv） | ⭐⭐⭐⭐ |
| **finance.ratings** | 分析师评级变化（Finviz/Benzinga，免费层） | ⭐⭐⭐ |
| **finance.industry-pulse** | 产业脉搏（TrendForce/DRAMeXchange 价格周报等） | ⭐⭐⭐⭐ |

在现有 `rss` 下新增 `finance` 类别：

```yaml
rss:
  # 现有 ai / crypto / tech 保持

  finance:
    # ==== filings - 年报/季报/披露 ====
    - {name: "SEC 10-K Latest",       url: "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=10-K&dateb=&owner=include&count=40&output=atom", tag: "filings"}
    - {name: "SEC 10-Q Latest",       url: "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=10-Q&dateb=&owner=include&count=40&output=atom", tag: "filings"}
    - {name: "SEC 8-K Latest",        url: "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=8-K&dateb=&owner=include&count=40&output=atom", tag: "filings"}
    - {name: "SEC 13F Latest",        url: "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=13F-HR&dateb=&owner=include&count=40&output=atom", tag: "filings"}
    - {name: "HKEXnews Today",        url: "https://www.hkexnews.hk/listedco/listconews/sehk/news/sehknews_today.xml", tag: "filings"}
    # 巨潮需爬虫（RSS 参数复杂）

    # ==== ir - 大厂投资者关系 ====
    - {name: "NVIDIA IR",             url: "https://nvidianews.nvidia.com/releases.xml", tag: "ir"}
    - {name: "Meta IR",               url: "https://investor.atmeta.com/rss/pressrelease.aspx", tag: "ir"}
    - {name: "Microsoft IR",          url: "https://www.microsoft.com/en-us/Investor/rss/pressrelease.aspx", tag: "ir"}
    - {name: "Alphabet IR",           url: "https://abc.xyz/investor/rss/press-releases/", tag: "ir"}
    - {name: "Tesla IR",              url: "https://ir.tesla.com/press-releases.rss", tag: "ir"}
    - {name: "Constellation Energy IR", url: "https://investors.constellationenergy.com/rss/pressrelease.aspx", tag: "ir"}
    - {name: "Vistra IR",             url: "https://investor.vistracorp.com/rss/pressrelease.aspx", tag: "ir"}
    - {name: "AMD IR",                url: "https://ir.amd.com/rss/news-releases.xml", tag: "ir"}
    - {name: "TSMC IR",               url: "https://pr.tsmc.com/english/rss.xml", tag: "ir"}
    - {name: "Micron IR",             url: "https://investors.micron.com/rss/pressrelease.aspx", tag: "ir"}

    # ==== bigtech-research - 大公司技术突破博客 ====
    # 美国大厂
    - {name: "NVIDIA Blog",           url: "https://blogs.nvidia.com/feed/", tag: "bigtech-research"}
    - {name: "NVIDIA Developer Blog", url: "https://developer.nvidia.com/blog/feed/", tag: "bigtech-research"}
    - {name: "Google AI Blog",        url: "https://blog.google/technology/ai/rss/", tag: "bigtech-research"}
    - {name: "Google Research Blog",  url: "https://research.google/blog/rss/", tag: "bigtech-research"}
    - {name: "Meta AI Blog",          url: "https://ai.meta.com/blog/rss/", tag: "bigtech-research"}
    - {name: "Meta Engineering",      url: "https://engineering.fb.com/feed/", tag: "bigtech-research"}
    - {name: "Microsoft Research",    url: "https://www.microsoft.com/en-us/research/feed/", tag: "bigtech-research"}
    - {name: "Apple ML Research",     url: "https://machinelearning.apple.com/rss.xml", tag: "bigtech-research"}
    - {name: "Amazon Science",        url: "https://www.amazon.science/index.rss", tag: "bigtech-research"}
    # 中国大模型独立公司
    - {name: "DeepSeek",              url: "https://api-docs.deepseek.com/news/rss", tag: "bigtech-research"}
    - {name: "Zhipu AI 智谱",         url: "https://www.zhipuai.cn/news/rss", tag: "bigtech-research"}  # URL 需验证
    - {name: "Moonshot AI 月之暗面",   url: "https://platform.moonshot.cn/blog/rss", tag: "bigtech-research"}  # URL 需验证
    - {name: "MiniMax",               url: "https://www.minimaxi.com/news/rss", tag: "bigtech-research"}  # URL 需验证
    - {name: "Baichuan 百川",         url: "https://www.baichuan-ai.com/blog/rss", tag: "bigtech-research"}  # URL 需验证
    - {name: "01.AI 零一万物",         url: "https://01.ai/blog/rss", tag: "bigtech-research"}  # URL 需验证

    # 中国互联网大厂 AI（字节/阿里/腾讯/华为/百度）
    # 注：中文大厂多数走微信公众号,标准 RSS 不完整,部分需要 RSSHub 代理
    # 字节跳动（Doubao/Seed/火山引擎）
    - {name: "字节 Seed (研究)",       url: "https://seed.bytedance.com/blog/rss", tag: "bigtech-research"}  # URL 需验证
    - {name: "火山引擎开发者博客",      url: "https://developer.volcengine.com/feed", tag: "bigtech-research"}  # URL 需验证
    - {name: "字节 HF (Seed/Doubao)",  url: "https://huggingface.co/bytedance-research/rss", tag: "bigtech-research"}  # HF 组织动态
    # 阿里（Qwen/DAMO）
    - {name: "阿里云开发者社区",        url: "https://developer.aliyun.com/feed", tag: "bigtech-research"}
    - {name: "Alibaba Qwen GitHub",   url: "https://github.com/QwenLM/Qwen.atom", tag: "bigtech-research"}  # GitHub releases
    - {name: "阿里 HF (Qwen)",        url: "https://huggingface.co/Qwen/rss", tag: "bigtech-research"}  # HF 组织动态
    - {name: "达摩院 DAMO Academy",    url: "https://damo.alibaba.com/events/rss", tag: "bigtech-research"}  # URL 需验证
    # 腾讯（Hunyuan / TEG）
    - {name: "腾讯云开发者社区",        url: "https://cloud.tencent.com/developer/rss", tag: "bigtech-research"}  # URL 需验证
    - {name: "腾讯 HF (Hunyuan)",     url: "https://huggingface.co/tencent/rss", tag: "bigtech-research"}
    - {name: "Tencent AI Lab",        url: "https://ai.tencent.com/ailab/en/news/rss", tag: "bigtech-research"}  # URL 需验证
    # 华为（盘古 / 鸿蒙 / 昇腾 AI）
    - {name: "华为开发者",             url: "https://developer.huawei.com/consumer/cn/blog/rss", tag: "bigtech-research"}  # URL 需验证
    - {name: "昇腾 Ascend",           url: "https://www.hiascend.com/blog/rss", tag: "bigtech-research"}  # URL 需验证
    # 百度（文心 / Apollo）
    - {name: "百度 AI 开发者",          url: "https://ai.baidu.com/support/news/rss", tag: "bigtech-research"}  # URL 需验证
    - {name: "百度 HF (ERNIE)",       url: "https://huggingface.co/baidu/rss", tag: "bigtech-research"}

    # 中国大厂 IR（港股 / 美股）
    - {name: "Tencent IR (00700.HK)",  url: "https://www.tencent.com/en-us/investors.rss", tag: "ir"}  # URL 需验证
    - {name: "Alibaba IR (BABA/9988)", url: "https://www.alibabagroup.com/news.xml", tag: "ir"}  # URL 需验证
    - {name: "JD.com IR",             url: "https://ir.jd.com/rss/news-releases.xml", tag: "ir"}  # URL 需验证
    - {name: "Baidu IR",              url: "https://ir.baidu.com/rss/news-releases.xml", tag: "ir"}  # URL 需验证

    # 注：大量中国源的 RSS URL 需要实施阶段 1 逐一验证。
    # 不可达源降级策略：
    #   1. 通过 RSSHub 代理（如 https://docs.rsshub.app/）
    #   2. 通过公众号订阅转 RSS（WeRSS / feed43）
    #   3. 定期手工抓 HTML（频率降到 weekly）
    #   4. 最后兜底：追踪其 GitHub / HuggingFace 组织动态（这些有稳定 API）

    # ==== vc-reports - VC/咨询行业分析 ====
    - {name: "a16z",                  url: "https://a16z.com/feed/", tag: "vc-reports"}
    - {name: "Sequoia Capital",       url: "https://www.sequoiacap.com/feed/", tag: "vc-reports"}
    - {name: "Bessemer Venture",      url: "https://www.bvp.com/atlas/feed", tag: "vc-reports"}
    - {name: "CB Insights",           url: "https://www.cbinsights.com/research-feed.xml", tag: "vc-reports"}
    - {name: "State of AI Report",    url: "https://www.stateof.ai/rss.xml", tag: "vc-reports"}  # URL 需验证
    - {name: "Stratechery (free)",    url: "https://stratechery.com/feed/", tag: "vc-reports"}
    - {name: "SemiAnalysis",          url: "https://semianalysis.com/feed/", tag: "vc-reports"}
    # 中国咨询（免费部分）
    - {name: "中国信通院白皮书",       url: "https://www.caict.ac.cn/rss/bps.xml", tag: "vc-reports"}  # URL 需验证
    - {name: "艾瑞咨询",              url: "https://www.iresearch.com.cn/rss/report.xml", tag: "vc-reports"}  # URL 需验证

    # ==== macro - 宏观数据 ====
    - {name: "FRED Recent Releases",  url: "https://fred.stlouisfed.org/releases/calendar/rss", tag: "macro"}
    - {name: "BLS Recent News",       url: "https://www.bls.gov/feed/news_release.rss", tag: "macro"}
    - {name: "Fed FOMC Statements",   url: "https://www.federalreserve.gov/feeds/press_monetary.xml", tag: "macro"}

    # ==== academic - 学术前沿 ====
    - {name: "arXiv cs.LG",           url: "http://export.arxiv.org/rss/cs.LG", tag: "academic"}
    - {name: "arXiv cs.CL",           url: "http://export.arxiv.org/rss/cs.CL", tag: "academic"}
    - {name: "arXiv cs.RO",           url: "http://export.arxiv.org/rss/cs.RO", tag: "academic"}  # 机器人

    # ==== ratings - 分析师评级变化（免费层）====
    - {name: "Benzinga Analyst Ratings", url: "https://www.benzinga.com/feed/analyst-ratings", tag: "ratings"}
    # Finviz 无官方 RSS,需要爬虫

    # ==== industry-pulse - 产业脉搏 ====
    - {name: "TrendForce",            url: "https://www.trendforce.com/news/feed", tag: "industry-pulse"}  # 半导体/存储/面板价格
    # DRAMeXchange 需要订阅(部分免费摘要)
    - {name: "CNCF Blog",             url: "https://www.cncf.io/feed/", tag: "industry-pulse"}  # 云原生风向
    - {name: "PitchBook Blog",        url: "https://pitchbook.com/blog/feed", tag: "industry-pulse"}  # 风投动态

schedules:
  # 现有配置保持
  # finance 沿用 daily（披露大多日级，不需要 hourly）
  # 例外：finance.filings 可考虑 4h（SEC 8-K 重大事件时效性敏感）

# ------------ GitHub Releases（补充，非 RSS 类）------------
# 关键 AI 开源项目的重大发布 = 技术突破先行指标
github_releases:
  repos:
    - {repo: "nvidia/cuda",          tag: "bigtech-research"}
    - {repo: "vllm-project/vllm",    tag: "bigtech-research"}
    - {repo: "sgl-project/sglang",   tag: "bigtech-research"}
    - {repo: "ollama/ollama",        tag: "bigtech-research"}
    - {repo: "langchain-ai/langgraph", tag: "bigtech-research"}
    - {repo: "huggingface/transformers", tag: "bigtech-research"}
    - {repo: "deepseek-ai/DeepSeek-V3", tag: "bigtech-research"}  # 大模型仓库
```

### 1.5 源清单覆盖度对照表

| 用户关心的类别 | 覆盖源 | Alpha 场景 |
|-------------|-------|----------|
| **年报季报** | SEC 10-K/10-Q + HKEX + 巨潮 | 财报 Beat/Miss + Guidance 跳空 → 加减仓触发 |
| **研报（卖方）** | Benzinga Analyst Ratings（免费层） + Seeking Alpha（P1 补） | 评级密集上调 = 共识形成苗头 |
| **研报（买方/VC）** | a16z / Sequoia / Bessemer / CB Insights / State of AI / SemiAnalysis | 早期赛道判断 + 主题识别 |
| **行业分析** | 信通院 / 艾瑞 / CNCF / PitchBook / TrendForce | 产业链量化 + 产能/价格数据 |
| **大公司技术突破** | NVIDIA Blog + Google AI + Meta AI + MS Research + Apple ML + Amazon Science + DeepSeek/Zhipu/Moonshot/MiniMax | Scaling Law / 产品发布 → 产业链传导信号 |
| **开源技术突破** | GitHub Releases（vLLM/SGLang/Ollama/LangGraph/Transformers/DeepSeek） | 新模型/框架爆发 = 产业链下一浪 |

### 2. LLM 分类打分 prompt 升级

在现有 prompt 加**金融关键词权重表**（触发 watchlist 相关词时提高评分）：

```python
# src/prompts/classify.py（或实际路径）添加：
FINANCE_KEYWORDS = {
    "ai_supply_chain": ["NVIDIA", "GPU", "HBM", "CPO", "光模块", "液冷", "核电", "CEG", "VST"],
    "embodied_ai": ["Optimus", "Figure", "人形机器人", "具身智能", "world model", "SpatialLM", "群核"],
    "large_model_ipo": ["MiniMax", "Zhipu", "智谱", "DeepSeek", "Moonshot", "港股 IPO"],
    "earnings_catalyst": ["capex", "guidance", "10-K", "10-Q", "8-K", "earnings call"],
}
```

匹配到关键词的条目评分加成 +10 到 +30，确保进入日报"金融"区块顶部。

### 3. 日报模板新增"金融"区块

`daily/YYYY/MM/DD.md` 顶部新增：

```markdown
## 💰 金融（finance-analysis 消费）

### 监管披露 / IR
- NVIDIA Q4 earnings call - Capex guidance $XXB (+XX% YoY) [NVDA +X%]
- HKEXnews 群核科技 (0068) 公告：XXX
- SEC 8-K: Meta 宣布 XXB AI Capex

### 宏观数据
- FRED: 10Y Treasury 收益率 +XXbps

### AI 产业链学术
- arXiv cs.RO: Tesla Optimus 新论文 X 篇...

---

## 🤖 AI（现有区块）
...
```

### 4. 对接 finance-analysis skill

在主 `.claude` 仓库新建 `skills/finance-analysis/references/integrations/rss-daily.md`：

```markdown
# rss-daily 集成契约

## 数据位置
~/workspace/rss/daily/YYYY/MM/DD.md

## 读取时机
finance-analysis skill 被调用时，若命题涉及"今日 Alpha"/"最近动态"，
先读取 ~/workspace/rss/daily/最新 3 天 的 md 文件

## 解析格式
Markdown - 重点关注"💰 金融"区块
每条新闻：标题 + 摘要 + URL + 评分

## 决策消费
- 匹配 watchlist 标的 → 直接触发决策卡
- 新浮现标的 → 加入 watchlist
- FOMO 峰值信号（覆盖度暴涨）→ 减仓警告
```

### 5. 黑名单同步

rss 仓库的 LLM 分类时应用 `~/.claude/skills/deep-research/references/sources/blacklist.yaml`：
- CSDN / 东财股吧 / 雪球 / 金色财经 等 hard 黑名单**直接过滤**
- soft 黑名单降级（不进"金融"区块，进"其他"区块）

---

## 风险与兜底

### 风险 1：RSS 源反爬 / UA 限制
- SEC EDGAR 对 User-Agent 有要求（必须符合 `User-Agent: Company Name AdminContact@domain.com`）
- 巨潮可能需要 JS 渲染
- **兜底**：`sources.yaml` 支持 `ua_override` 字段；反爬源降级为"每周手工"

### 风险 2：金融新闻信噪比低
- 如果每天 50+ 条金融新闻但只有 2 条 Alpha 相关，日报会被污染
- **兜底**：LLM 评分 + `top_n_per_category` 限制（现有能力，设 20-30）

### 风险 3：skill 和 rss 代码耦合
- 如果 skill 读 rss 输出，rss 改 MD 格式会破坏 skill
- **兜底**：MD 格式作为**契约文档**（见 integrations/rss-daily.md），改动需同步

### 风险 4：频率过高触发对方封禁
- SEC EDGAR / HKEXnews 有 rate limit
- **兜底**：daily schedule + 随机延时（复用现有 `delay_ms`）

---

## 后续扩展方向（P2）

不在本轮，但预留空间：
1. **卖方研报聚合**（东财 / 慧博）
2. **年报深度解析**（100 页 10-K 用 LLM 抽取关键字段）
3. **警报推送**（企业微信 / 邮件）
4. **跨源交叉验证**（同一事件多源确认 → 高置信）
5. **情绪指标**（X FinTwit 情绪 + Reddit WSB 温度计）

---

## 验收标准

阶段 1 完成时：
- [ ] `sources.yaml` 含 finance 类别，至少 10 个源
- [ ] 跑 1 周日报，金融区块每天 ≥ 10 条
- [ ] 至少识别 1 个 AI 产业链 Alpha 信号（可主观评估）

阶段 2 完成时：
- [ ] `finance-analysis` skill 可读 rss daily 文件
- [ ] worked example：给出"今日 Alpha 巡检"输出

阶段 3（未来）：
- [ ] 月度自动化压缩到 15 分钟
- [ ] 任何 AI 子赛道启动 ≤ 3 月被识别（对齐 skill 的 KPI）

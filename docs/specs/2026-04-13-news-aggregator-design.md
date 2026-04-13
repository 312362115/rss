# 每日新闻聚合器 — 技术方案

| 项 | 内容 |
|----|------|
| 版本 | v0.1 |
| 日期 | 2026-04-13 |
| 状态 | 待评审 |
| 关联 Backlog | `docs/backlog/2026-04-13-news-aggregator.md` |
| 关联 Plan | `docs/plans/2026-04-13-news-aggregator-plan.md` |

---

## 1. 背景与动机

### 1.1 问题

目前跟踪 AI / 币圈 / 科技圈一手信息依赖**手动刷 X + Reddit + HN + 若干媒体 RSS**,存在三个痛点:

1. **信息密度低**:10 分钟刷下来 90% 是噪音,真正"出圈"的头条常常漏掉
2. **跨圈覆盖难**:AI 圈和币圈在 X 上是两个信息泡,刷完一圈要花 20+ 分钟
3. **时效要求高**:X 是海外一手消息最快的渠道,但手动刷时段不固定,错过热点

### 1.2 目标

实现一个**个人情报聚合器**:
- 本地每 4 小时自动抓取 AI / 币圈 / 科技圈的关键信息源
- LLM 打分筛选,自动分类(AI / 币圈 / 科技)
- 输出**中文日报 Markdown**,直接落盘到 private git 仓库
- 通过 GitHub 网页的 MD 原生渲染查看,不搞静态站

### 1.3 范围界定

**做**:
- X(小号 cookie)+ HN + Reddit + 媒体 RSS 的采集、打分、分类、渲染
- launchd 本地定时任务
- 单仓(private),脚本 + 日报 MD 同仓,`git push` 到 GitHub
- 中文日报(标题原文 + 中文一句话点评)

**不做**:
- X 官方 API(免费层 100 读/月,不够用)
- GitHub Pages / Jekyll / 任何静态站(看 MD 直接靠 GitHub 网页的原生渲染)
- 任何去重(跨时段/跨源,每个 4h 独立)
- 复杂全文抓取(只抓标题 + 摘要 + 链接,不爬正文)
- 主动推送(TG / 邮件 / 飞书)
- 用户登录 / 多租户
- 可视化图表 / 趋势分析
- macOS 睡眠时的补跑机制

---

## 2. 现状分析

项目仓库为空(`~/workspace/rss/`),纯绿地开发。无历史决策可参考,MEMORY.md 也无相关记录。

---

## 3. 调研与备选方案

### 3.1 X 抓取方案

这是**最高风险、最需要验证**的部分,2026-04 的 X 反爬现状决定了整个项目成立性。

#### 方案 A:X 官方 API 免费层

- **调研**:访问 developer.x.com 免费层文档
- **结果**:免费层 100 reads / 月,完全不够用(6 次/天 × 30 天 × 至少 50 条 = 9000 reads/月)
- **结论**:❌ 排除

#### 方案 B:RSSHub Twitter 路由(Docker 自建)

- **调研**:GitHub Issues #19420 / #16014,社区反馈
- **结果**:
  - 仍在维护,需要 `auth_token` + `ct0` cookie
  - 2025/2026 频繁报告 "Twitter cookie for token is not valid" 间歇性失效
  - 需要常驻 Docker,多一层 HTTP 中间件
- **结论**:⚠️ 可用但额外复杂度高

#### 方案 C:twscrape(Python 账号池库)

- **调研**:GitHub vladkens/twscrape,2026-03 验证可用
- **结果**:
  - 账号池设计,自动轮换避免限流
  - 需要真实账号登录
  - X 每 2-4 周更新反爬,维护成本 10-15 h/月
- **结论**:⚠️ 可用,作为 fallback

#### 方案 D:xreach-cli(npm 包,原名 xfetch)

- **调研**:Panniantong/xfetch GitHub,Agent-Reach 生态指向的 X 抓取工具
- **验证**:已本地安装 `npm install -g xreach-cli`,运行 `xreach --help` 成功
- **能力**:
  - cookie 直接从 Chrome/Firefox/Safari/Arc/Brave 读取:`xreach auth extract --browser chrome`
  - 命令:`xreach tweets <handle>` / `xreach list-tweets <id>` / `xreach search <query>`
  - 输出:json / jsonl / csv / sqlite,带分页、重试、代理、delay
  - 内置 session pool(作者同一个,与 Agent-Reach 共享)
  - 内部会 auto-refresh query ID(X 反爬更新时自动适配)
- **优点**:
  1. 单可执行文件(`xreach`),无需 Docker / HTTP 中间层
  2. 从 Python 通过 `subprocess` 直接调用,架构极简
  3. 反爬自适应 + session pool,比 RSSHub 更省心
  4. 原生 JSONL 输出方便去重
- **结论**:✅ **主路径**

#### 方案 E:Nitter

- **调研**:公共实例列表
- **结果**:2024/01 被 X 封 guest token 后公共实例几乎全挂,仅少数靠轮换账号苟活
- **结论**:❌ 排除

### 3.2 X 抓取决策

| 方案 | 决定 |
|------|------|
| **主路径** | **xreach-cli** |
| **备用(v0.2)** | twscrape(仅当 xreach 连续失效 3 次时引入) |
| 排除 | 官方 API / Nitter / RSSHub(RSSHub 过于重) |

**取舍**:
- **放弃**了"AI 抓取能力作为 skill 复用"(不装 Agent-Reach 本体,只用底层 CLI)
- **换取**了架构极简(单文件 CLI + subprocess 调用,无 Docker)
- **遗留风险**:xreach 作者是个人项目,如果停止维护需要切 twscrape

### 3.3 非 X 数据源

所有方案均已 `curl` 实测通过:

| 源 | 接口 | 成本 | 验证 |
|----|------|------|------|
| HackerNews | Firebase API (`topstories.json` + `item/<id>.json`) | 免费无限 | ✅ 已验证 |
| Reddit | `<subreddit>.json` 后缀 | 免费,需自定义 UA | ✅ 已验证 |
| RSS 媒体 | `feedparser` | 免费 | 库成熟 |
| arxiv / HF Daily Papers | 官方 RSS/JSON | 免费 | 库成熟 |

### 3.4 LLM 打分方案

#### 方案 A:Anthropic Python SDK + API key

- 成本:$3/1M input,每天 6 次 × ~100 条打分 = 约 $5-10/月
- 稳定、可编程
- 需单独管理 API key

#### 方案 B:Claude Code CLI(`claude -p "<prompt>"`)

- **成本:$0**(用户已订阅 Claude Max,CLI 免费用)
- 延迟略高(一次调用 10-30s)
- 需处理 stdin/stdout,返回格式不如 SDK 可靠,但可以约束 prompt 输出 JSON

#### 方案 C:Gemini 2.0 Flash 免费层

- 1500 req/day,质量够用
- 需单独申请 key,增加管理项

#### 决策:**方案 B(Claude Code CLI)**

**核心理由**:零边际成本,用户已有订阅,本项目是个人用途不追求极致稳定。

**取舍**:放弃了 API 的编程便利性和并发能力,每次打分串行跑 10-30s(每 4h 一次可接受)。

**Prompt 约束**:强制输出 JSON,解析失败时降级为"按发布时间排序取 Top N"而非报错中断。

### 3.5 静态站方案

**决策:不做静态站**。理由:
- 用户决定日报直接落在 private 仓库内,靠 GitHub 网页对 MD 的原生渲染查看
- 省掉 Jekyll / Pages / build step / 主题管理 / 结果仓维护
- 权衡:没有侧栏导航和搜索,但当前日报规模(一天一文件)用 GitHub 网页的目录树就够
- 遗留:如果未来要上 Pages,在 `daily/` 目录上开一个即可,不影响现有结构

### 3.6 去重方案

| 方案 | 优劣 |
|------|------|
| JSON 文件 hash set | 简单但并发写不安全 |
| **SQLite** | 带索引、去重 + 按时间清理方便 | ✅ 选 |
| Redis | 过度设计 |

**决策:SQLite**,`state/seen.sqlite` 存 `(source, id, url, seen_at)`,7 天滚动清理。

### 3.7 UA 策略

| 源 | UA 需求 | 采用 |
|----|---------|------|
| HN | 不需要 | 空 |
| Reddit | 必须自定义,禁止伪装浏览器 | `rss-daily/0.1 by renlongyu` |
| RSS 媒体 | 多数不需要 | 描述性 UA `rss-daily/0.1 (+https://github.com/renlongyu/rss-daily)` |
| 特定 CF 保护站 | 有时要浏览器 UA | `sources.yaml` 里单独 override |
| xreach | 工具内处理 | — |

**决策原则**:**描述性 UA 优先,不装浏览器**。Reddit TOS 明确禁止浏览器伪装,且描述性 UA 让站点方能联系你(而不是直接封 IP)。个别 CF 站单独在 `sources.yaml` 里 override。

### 3.8 定时触发

| 方案 | 决策 |
|------|------|
| launchd (`StartCalendarInterval`) | ✅ 选,macOS 原生 |
| cron | 不用,launchd 更现代 |
| GH Actions 兜底 | 不加(用户接受偶发丢失) |

---

## 4. 决策总览

| 决策点 | 选择 | 核心理由 |
|--------|------|----------|
| X 抓取 | `xreach-cli` | 单文件 CLI,session pool + 自适应反爬,不需要 Docker |
| X 失效兜底(v0.2) | twscrape | 同作者生态外的独立方案 |
| HN | Firebase API | 免费无限,官方 |
| Reddit | `.json` 直接请求 | 免 key,符合 TOS |
| RSS 媒体 | `feedparser` | 库成熟 |
| LLM 打分 | Claude Code CLI (`claude -p`) | 零成本(用户已订阅) |
| 静态站 | **不做** | 直接用 GitHub 网页原生 MD 渲染 |
| 去重 | **单次 slot 内跨源 URL 去重(in-memory)** | 同一 URL 多源命中按 X > HN > Reddit > RSS 保留;**跨时段不去重**,重要事件靠时段重复自然展示 |
| 定时 | launchd | macOS 原生 |
| UA | 描述性 UA,非浏览器伪装 | 合规 + 好维护 |
| 仓库 | **单仓 private** | 脚本 + 日报同仓,极简 |

---

## 5. 技术方案

### 5.1 整体架构

```
┌─────────────────── 本地 Mac ──────────────────┐
│                                                │
│  launchd (每 4h 触发)                          │
│     │                                          │
│     ↓                                          │
│  ~/workspace/rss/src/main.py                   │
│     │                                          │
│     ├─ fetch/  并行抓取                        │
│     │    ├─ x_fetcher.py   → subprocess xreach │
│     │    ├─ reddit_fetcher.py → requests       │
│     │    ├─ hn_fetcher.py  → requests          │
│     │    └─ rss_fetcher.py → feedparser        │
│     │                                          │
│     ├─ classify + rank                         │
│     │    → subprocess `claude -p` 输出 JSON    │
│     │                                          │
│     ├─ render (Jinja2 → MD)                    │
│     │                                          │
│     └─ publish                                 │
│          ↓ write                               │
│      ~/workspace/rss/daily/YYYY/MM/DD.md       │
│          ↓                                     │
│      git add / commit / push(同仓 origin)     │
│                                                │
└────────────────────────────────────────────────┘
                        │
                        ↓ git push
              ┌──────────────────────┐
              │ github.com/312362115/ │
              │  rss (private)        │
              │                       │
              │ (通过网页浏览 MD 即可)│
              └──────────────────────┘
```

### 5.2 目录结构

**单仓库** `~/workspace/rss/`(private,remote:`git@github.com:312362115/rss.git`):

```
rss/
├── .gitignore                   # 忽略 .secrets/ .venv/ __pycache__/
├── README.md
├── pyproject.toml               # Python 依赖
├── sources.yaml                 # KOL + RSS + subreddit 配置
├── prompts/
│   └── classify.md              # 分类 + 打分 prompt 模板
├── src/
│   ├── __init__.py
│   ├── main.py                  # 主流程入口
│   ├── config.py                # 加载 sources.yaml
│   ├── fetch/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── x_fetcher.py
│   │   ├── reddit_fetcher.py
│   │   ├── hn_fetcher.py
│   │   └── rss_fetcher.py
│   ├── rank.py                  # claude CLI 打分 + 分类
│   ├── render.py                # 渲染 MD
│   ├── publish.py               # 写入 daily/ + git commit/push
│   └── templates/
│       └── daily.md.j2
├── daily/                       # ← 日报落地目录,git 跟踪
│   ├── INDEX.md                 # 简单索引(可选,每天追加一行)
│   └── 2026/
│       └── 04/
│           ├── 13.md
│           └── 14.md
├── .secrets/                    # (gitignore)
│   └── x_cookie_notes.md        # 小号信息备忘
├── launchd/
│   └── com.renlongyu.rss.plist
├── docs/
│   ├── specs/
│   ├── plans/
│   ├── backlog/
│   ├── runbooks/
│   ├── decisions/
│   └── tests/
└── tests/
    └── test_*.py
```

**说明**:
- `daily/` 目录与 `src/` 同仓,同一个 `git push` 一次搞定
- GitHub 网页对 private 仓 MD 有原生渲染(侧边栏显示目录树,点 `daily/2026/04/13.md` 即可阅读)
- `daily/INDEX.md` 可选:每次 slot 运行时往里追加一行"日期 · slot · 文件链接",作为简单归档索引

### 5.3 数据流

```
┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐
│  xreach    │  │   HN API   │  │  Reddit    │  │   RSS      │
└─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
      │               │               │               │
      └───────┬───────┴───────┬───────┴───────┬───────┘
              │               │               │
              ↓               ↓               ↓
        ┌──────────────────────────────────────────┐
        │  Item(source, id, title, url, url_hash,  │
        │  text, author, published_at,             │
        │  raw_score, normalized_score)            │
        └───────────────────┬──────────────────────┘
                            │
                            ↓
                    ┌───────────────┐
                    │ dedup_in_slot │ 单次 slot 内 URL 去重
                    └───────┬───────┘
                            │
                            ↓  (in-memory, no state)
                    ┌───────────────┐
                    │   rank.py     │ ← claude -p (importance + density)
                    └───────┬───────┘
                            │
                            ↓  final_score = imp + den + norm
                    ┌───────────────┐
                    │    sort       │ → 每类 Top 20
                    └───────┬───────┘
                            │
                            ↓  RankedItem list
                    ┌───────────────┐
                    │  render.py    │ → MD section(倒序插入)
                    └───────┬───────┘
                            │
                            ↓
                    ┌───────────────┐
                    │  publish.py   │ → rss-daily git push
                    └───────────────┘
```

### 5.4 关键模块

#### 5.4.1 `sources.yaml` 结构

```yaml
meta:
  user_agent_default: "rss-daily/0.1 (+https://github.com/312362115/rss)"
  reddit_user_agent: "rss-daily/0.1 by renlongyu"
  top_n_per_category: 20        # 每类最多写入的条数
  rss_items_per_feed: 10        # 每个 RSS feed 抓的最新条数
  # 热度归一化封顶阈值(见 §5.6.4)
  hotness_caps:
    hn_score: 500
    reddit_upvotes: 5000
    x_favorites: 10000

x:
  # xreach 调用参数
  cookie_browser: chrome       # 从哪个浏览器读 cookie
  delay_ms: 1500
  # 方式 1:list(推荐,一次请求拿多人时间线)
  lists:
    - name: ai-core
      id: "<list_id>"
      tweets_per_run: 50
    - name: crypto-core
      id: "<list_id>"
      tweets_per_run: 50
  # 方式 2:单人 fallback(某些 KOL 不适合塞 list)
  users:
    - handle: zachxbt
      tweets_per_run: 20

hackernews:
  top_count: 30
  min_score: 100

reddit:
  ai:
    - {sub: singularity,    sort: top, t: day, limit: 10}
    - {sub: LocalLLaMA,     sort: top, t: day, limit: 10}
    - {sub: MachineLearning,sort: top, t: day, limit: 5}
    - {sub: OpenAI,         sort: top, t: day, limit: 5}
    - {sub: ClaudeAI,       sort: top, t: day, limit: 5}
  crypto:
    - {sub: CryptoCurrency, sort: top, t: day, limit: 10}
    - {sub: Bitcoin,        sort: top, t: day, limit: 5}
    - {sub: ethereum,       sort: top, t: day, limit: 5}
    - {sub: solana,         sort: top, t: day, limit: 5}
  tech:
    - {sub: technology,     sort: top, t: day, limit: 5}
    - {sub: programming,    sort: top, t: day, limit: 5}

rss:
  ai:
    - {name: Anthropic,     url: "https://www.anthropic.com/news/rss.xml"}
    - {name: OpenAI Blog,   url: "https://openai.com/blog/rss.xml"}
    - {name: DeepMind,      url: "https://deepmind.google/blog/rss.xml"}
    - {name: HF Papers,     url: "https://huggingface.co/papers/feed/daily"}
    - {name: MIT Tech Review AI, url: "https://www.technologyreview.com/topic/artificial-intelligence/feed"}
    - {name: Simon Willison,url: "https://simonwillison.net/atom/everything/"}
  crypto:
    - {name: CoinDesk,      url: "https://www.coindesk.com/arc/outboundfeeds/rss/"}
    - {name: The Block,     url: "https://www.theblock.co/rss.xml"}
    - {name: Decrypt,       url: "https://decrypt.co/feed"}
    - {name: Cointelegraph, url: "https://cointelegraph.com/rss"}
    - {name: Bankless,      url: "https://newsletter.banklesshq.com/feed"}
  tech:
    - {name: TechCrunch,    url: "https://techcrunch.com/feed/"}
    - {name: The Verge,     url: "https://www.theverge.com/rss/index.xml"}
    - {name: Ars Technica,  url: "https://feeds.arstechnica.com/arstechnica/index"}
    - {name: HN Front Page, url: "https://hnrss.org/frontpage"}
  # 单个源需要特殊 UA 时:
  # - {name: xxx, url: "...", ua_override: "Mozilla/5.0 ..."}
```

KOL 清单与 X list 映射见**附录 A**。

#### 5.4.2 `fetch/base.py` 数据结构

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

Source = Literal["x", "hn", "reddit", "rss"]

Source = Literal["x", "hn", "reddit", "rss"]

# 单次 slot 内跨源 URL 去重时的优先级:X > HN > Reddit > RSS
# 同一 URL 多源命中时,保留优先级最高的那条
SOURCE_PRIORITY: dict[Source, int] = {"x": 0, "hn": 1, "reddit": 2, "rss": 3}

@dataclass
class Item:
    source: Source
    id: str                      # 源内唯一 ID(供日志追踪)
    url: str                     # 原始 URL
    url_hash: str                # normalize_url(url) 的 sha1 前 16 位,单次 slot 内去重主键
    title: str
    text: str                    # 摘要/正文(<=500字符)
    author: str                  # X handle / Reddit user / RSS feed name
    published_at: datetime
    raw_score: float = 0.0       # 源头自带的热度(HN score, Reddit upvote, X fav)
    normalized_score: float = 0.0  # 代码算的"热度信号",0-30,源内归一化(见 §5.6)
    source_meta: dict = field(default_factory=dict)

@dataclass
class RankedItem:
    item: Item
    category: Literal["ai", "crypto", "tech", "skip"]
    score: float                 # LLM 打分 0-100
    comment_cn: str              # 中文一句话点评
```

**去重策略**:
- **单次 slot 内**:跨源 URL 去重(in-memory,无 SQLite)。同一规范化 URL 多源命中时,按 `SOURCE_PRIORITY` (X > HN > Reddit > RSS) 保留优先级最高的那条,丢弃其他
- **跨时段**:**不去重**。同一条新闻在 04:00 和 12:00 都抓到会同时出现在两个时段——这是特性,因为持续出现本身就是"重要性"的信号

#### 5.4.2a URL 规范化(单次 slot 内去重依赖)

```python
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
import hashlib

TRACK_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "ref_src", "ref_url", "mc_cid", "mc_eid", "fbclid", "gclid",
    "s",                # x.com 分享追踪
}

def normalize_url(url: str) -> str:
    p = urlparse(url.strip())
    scheme = "https"
    netloc = p.netloc.lower().removeprefix("www.")
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=False)
         if k not in TRACK_PARAMS]
    query = urlencode(sorted(q))
    path = p.path.rstrip("/") or "/"
    return urlunparse((scheme, netloc, path, "", query, ""))

def url_hash(url: str) -> str:
    return hashlib.sha1(normalize_url(url).encode()).hexdigest()[:16]


def dedup_in_slot(items: list[Item]) -> list[Item]:
    """单次 slot 内跨源去重,保留优先级最高的源"""
    by_hash: dict[str, Item] = {}
    for it in items:
        prev = by_hash.get(it.url_hash)
        if prev is None or SOURCE_PRIORITY[it.source] < SOURCE_PRIORITY[prev.source]:
            by_hash[it.url_hash] = it
    return list(by_hash.values())
```

#### 5.4.3 `x_fetcher.py` 调用示例

```python
# 关键调用:
# xreach list-tweets <list_id> -n 50 --format jsonl --delay 1500
# xreach tweets <handle>       -n 20 --format jsonl --delay 1500
#
# cookie 管理:一次性 xreach auth extract --browser chrome
# 之后 xreach 内部持久化,不用每次传

def fetch_list(list_id: str, count: int = 50) -> list[Item]:
    proc = subprocess.run(
        ["xreach", "list-tweets", list_id,
         "-n", str(count), "--format", "jsonl", "--delay", "1500"],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        log.warning(f"xreach failed: {proc.stderr}")
        return []
    return [parse_tweet_jsonl(line) for line in proc.stdout.splitlines() if line]
```

#### 5.4.4 `rank.py` LLM 调用

**Prompt 模板**(`prompts/classify.md`):

```
你是一个新闻编辑助手,从 AI / 币圈 / 科技 三个领域分类和评估每条内容。

输入:JSON 数组,每条 {id, title, text, author, source, url}
输出:严格 JSON 数组,每条 {id, category, importance, density, comment_cn}

你只评两个维度(其他维度由代码算,不归你管):

- importance (0-40):这件事在本领域重要吗?
  官方发布 / 重要人物决策 / 技术突破 / 重大事件 → 30-40
  行业动态 / 有价值的分析 → 15-29
  日常讨论 / 普通新闻 → 0-14

- density (0-30):文本信息密度
  包含具体事实、数字、名字、链接 → 20-30
  中等事实,有一些细节 → 10-19
  情绪 / 营销话术 / 水文 → 0-9

分类 category:
- ai:大模型、AI 产品、Labs 动态、ML 研究
- crypto:BTC/ETH/SOL 行情、协议、监管、链上事件
- tech:非 AI 科技(芯片、消费电子、互联网公司新闻)
- skip:水文 / 广告 / 重复 / 不相关

每条 comment_cn:中文一句话点评,点明"为什么值得看"。

输入:
{items_json}

只输出 JSON,不要任何其他文字。
```

**总分合成(代码层)**:

```python
# rank.py 收到 LLM 返回后
def final_score(item: Item, llm_importance: float, llm_density: float) -> float:
    return llm_importance + llm_density + item.normalized_score
    # 最高 40 + 30 + 30 = 100
```

**排序**(每类 Top 20):
1. 过滤 `category == "skip"`
2. 按 `category` 分组(AI / 币圈 / 科技)
3. 每组按 `final_score` 降序
4. 每组取前 **20** 条

每时段最多写 60 条(3 类 × 20),一天 6 时段 = 最多 360 条。实际 LLM 分类后可能某些类不足 20 条,按实际取。

**调用**:
```python
def rank_items(items: list[Item]) -> list[RankedItem]:
    prompt = PROMPT_TEMPLATE.format(items_json=to_json(items))
    proc = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True, text=True, timeout=120,
    )
    try:
        return parse_ranked_json(proc.stdout)
    except JSONDecodeError:
        log.error("LLM output parse failed, fallback to raw_score sort")
        return fallback_rank(items)
```

**批大小**:一次最多塞 100 条,超过则分批。每条 ~200 token 输入,100 条约 20k token,Claude 可轻松处理。

#### 5.4.5 `render.py` 输出格式

只有一种运行模式(slot)。每次运行抓新条目 → 写入当天 MD 文件 → 把新时段节**插到所有已有时段的上方**(倒序,新的在顶)。

每日 MD 文件示例 `daily/2026/04/13.md`(假设一天跑了 3 次 8:00 / 12:00 / 16:00):

```markdown
# 2026-04-13

<!-- SLOTS_BEGIN -->

## 16:00 时段  ← 最新时段永远在顶

### AI
1. **[Anthropic 发布 Claude Opus 4.6 1M context](https://...)**
   - 出处:@AnthropicAI · score 96
   - 点评:上下文窗口进入百万 token 时代,编程场景长项目分析不再需要 RAG

2. ...

### 币圈
1. ...

### 科技
1. ...

## 12:00 时段

### AI
...

## 08:00 时段

### AI
...

<!-- SLOTS_END -->
```

**写入规则**:
- 首次创建文件:写 `# 日期` + `<!-- SLOTS_BEGIN -->` + `<!-- SLOTS_END -->`(不加 front-matter,GitHub 原生渲染用不上)
- 每次 slot 运行:将新时段节**插入到 `<!-- SLOTS_BEGIN -->` 的下一行**(即所有已有时段之上)
- 幂等性:每次运行前先检查"本日本时段是否已存在",已存在则跳过(防止同一 4h 内重复跑的情况)
- 没有汇总、没有总榜,所有信息都在各自时段内

#### 5.4.6 `publish.py`

```python
REPO_ROOT = Path(__file__).resolve().parents[2]   # ~/workspace/rss

def publish(slot_md: str, date: date, slot: str):
    """
    slot_md: render.py 生成的当前时段的 MD 内容(## HH:00 时段 ... 三分类)
    写入 ~/workspace/rss/daily/YYYY/MM/DD.md,git push 到 origin(同仓 private)
    """
    target = REPO_ROOT / "daily" / f"{date.year}" / f"{date.month:02d}" / f"{date.day:02d}.md"
    target.parent.mkdir(parents=True, exist_ok=True)

    # 首次创建:写 front-matter + "# 日期" + SLOTS_BEGIN/END 占位
    if not target.exists():
        target.write_text(render_skeleton(date))

    content = target.read_text()
    # 幂等:本时段已存在则跳过
    if f"## {slot} 时段" in content:
        log.info(f"slot {slot} already exists in {target.name}, skip")
        return

    # 把新时段节插到 SLOTS_BEGIN 的下一行(倒序:最新在顶)
    content = content.replace(
        "<!-- SLOTS_BEGIN -->\n",
        f"<!-- SLOTS_BEGIN -->\n\n{slot_md}\n",
        1,
    )
    target.write_text(content)

    subprocess.run(["git", "-C", str(REPO_ROOT), "pull", "--rebase"], check=False)
    subprocess.run(["git", "-C", str(REPO_ROOT), "add", "daily/"], check=True)
    subprocess.run(
        ["git", "-C", str(REPO_ROOT), "commit", "-m", f"daily: {date} {slot}"],
        check=True,
    )
    subprocess.run(["git", "-C", str(REPO_ROOT), "push"], check=True)
```

**注意**:`git add daily/` 而非 `git add .`,避免把 `.secrets/` 之外的代码改动一起 commit——代码变更另起 commit,两类 commit 分开管理。

### 5.5 launchd 配置

`launchd/com.renlongyu.rss.plist`(装到 `~/Library/LaunchAgents/`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.renlongyu.rss</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/renlongyu/workspace/rss/.venv/bin/python</string>
    <string>/Users/renlongyu/workspace/rss/src/main.py</string>
  </array>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Hour</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>4</integer></dict>
    <dict><key>Hour</key><integer>8</integer></dict>
    <dict><key>Hour</key><integer>12</integer></dict>
    <dict><key>Hour</key><integer>16</integer></dict>
    <dict><key>Hour</key><integer>20</integer></dict>
  </array>

  <key>StandardOutPath</key><string>/tmp/rss-daily.log</string>
  <key>StandardErrorPath</key><string>/tmp/rss-daily.err</string>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
```



### 5.6 数量预算与打分策略(集中说明)

#### 5.6.1 每次运行的抓取预算

| 源 | 单次抓取 cap | 预期条数 | 备注 |
|----|-------------|---------|------|
| X lists(4 个) | 每 list `-n 50` | ~200 | xreach list-tweets |
| X users(单独) | 每 user `-n 20` | ~20 | 目前只有 @zachxbt |
| HN | top 30 中过滤 `score>=100` | ~15 | Firebase API |
| Reddit(14 个 sub) | 每 sub top 5-10 | ~100 | `sort=top&t=day` |
| RSS(~15 个源) | 每源最新 **10** 条 | ~150 | feedparser |
| **总计** | | **~485** | |

**RSS 每源 limit**:**10**(定稿)

#### 5.6.2 数据流中的数量漏斗

```
抓取(~485)
    ↓
单次 slot 内 URL 去重(~400,跨源命中约 15-20%)
    ↓
打分(Claude CLI 分批 100/批,共 ~4 批)
    ↓
过滤 skip(~30-50% 被丢)
    ↓
每类 Top 20,按类分组
    ↓
写入 MD(每时段最多 60 条,实际 30-60)
```

**Top N per category**:**20**(每时段最多 60 条,一天最多 360 条)

#### 5.6.3 打分三维(两维 LLM + 一维代码)

| 维度 | 谁打 | 分值 | 说明 |
|------|------|------|------|
| **importance** | LLM | 0-40 | 话题在本领域的重要性 |
| **density** | LLM | 0-30 | 文本信息密度(事实/数字/名字 vs 水文) |
| **normalized_score** | 代码 | 0-30 | `raw_score` 源内归一化(见 §5.6.4) |
| **总分** | 合成 | 0-100 | 三项相加 |

**被砍掉的维度及原因**:
- ❌ 新鲜度:4h 窗口内所有内容都"新",无区分度
- ❌ 跨圈传播度:单条内容上 LLM 无真实传播数据,只会重复算"重要性"。真正的破圈需要时间,重要的事件在下一个 4h 仍会出现,靠时段重复自然展示

#### 5.6.4 热度归一化 `normalize_score`

每个 fetcher 在返回 `Item` 前计算 `normalized_score`(0-30):

```python
# fetch/hn_fetcher.py
def _normalize(hn_score: int) -> float:
    return min(hn_score / 500, 1.0) * 30  # HN 500 分封顶

# fetch/reddit_fetcher.py
def _normalize(upvotes: int) -> float:
    return min(upvotes / 5000, 1.0) * 30  # Reddit 5k upvotes 封顶

# fetch/x_fetcher.py
def _normalize(favorites: int) -> float:
    return min(favorites / 10000, 1.0) * 30  # X 1w 点赞封顶

# fetch/rss_fetcher.py
def _normalize(index_in_feed: int, total: int) -> float:
    # RSS 无自带热度,按 feed 返回顺序(靠前认为越新/越显眼)
    return (1 - index_in_feed / max(total, 1)) * 30
```

**封顶阈值**依据:凭经验,首版跑几天观察实际分数分布后可微调。阈值写在 `sources.yaml` 的 `meta` 下,不要硬编码。



Python(`pyproject.toml`):
- `requests`
- `feedparser`
- `pyyaml`
- `jinja2`
- `python-dateutil`

系统:
- `node >= 18`(已有 25.9.0)
- `xreach-cli`(已 `npm i -g`)
- `claude` CLI(已有,Claude Code 订阅)
- `git`

---

## 6. 风险与边界

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| X 反爬更新导致 xreach 失效 | 中(2-4 周一次) | 高(X 是主源) | xreach 作者自适应 + 手动更新 + twscrape fallback |
| 小号被风控 / 封号 | 中 | 高 | 新号养 3-7 天、关注 50+、不绑主号手机 |
| cookie 过期 | 高(~2-4 周) | 中 | 记录在 runbook 里,定期 `xreach auth extract` |
| Mac 睡眠错过触发 | 高 | 低(已接受) | 不处理 |
| RSS 源 403 / 改版 | 低 | 低 | `sources.yaml` 单源禁用 + `ua_override` |
| Claude CLI 限流 / 输出格式漂移 | 低 | 中 | 降级到 raw_score 排序 |
| git push 冲突(多设备?) | 低 | 低 | 先 pull 后 push,冲突则跳过本次 |
| LLM 误判分类 | 中 | 低 | 可接受,后续优化 prompt |
| 同一新闻跨时段重复出现 | 高 | 低 | 设计选择,不处理。如果阅读体验变差,v0.2 可加"同一时段内 URL 内存级去重" |

---

## 7. 未来演进

明确**不在 v0.1 范围**的扩展点(避免当前设计承担假想复杂度):

- v0.2:twscrape fallback + cookie 自动检查告警
- v0.3:增加 Farcaster / Mastodon 源作为 X 替代
- v0.4:按时段生成日摘要(跨 6 次时段的 top 总结)
- v0.5:TG / 邮件订阅推送

---

## 附录 A:KOL 清单(起点)

以下是 X list 的起点名单,分 ai / crypto / tech / 中文 四类。实际 list 的**创建和 id 在执行阶段**获取。

### ai-core(25 人)

| handle | 备注 |
|--------|------|
| sama | OpenAI CEO |
| gdb | OpenAI President |
| miramurati | Mira Murati |
| demishassabis | DeepMind CEO |
| elonmusk | xAI(噪音大但出圈) |
| AnthropicAI | 官方 |
| OpenAI | 官方 |
| GoogleDeepMind | 官方 |
| alexalbert__ | Anthropic DevRel |
| karpathy | Andrej Karpathy |
| ylecun | Yann LeCun |
| drjimfan | Jim Fan (NVIDIA) |
| _jasonwei | Jason Wei (CoT) |
| jeremyphoward | fast.ai |
| mervenoyann | HF,论文速递 |
| emollick | Ethan Mollick |
| simonw | Simon Willison |
| swyx | AI Engineer 社区 |
| goodside | Riley Goodside |
| rauchg | Vercel |
| natfriedman | Nat Friedman |
| bindureddy | Bindu Reddy |
| ashvardanian | — |
| ilyasut | Ilya Sutskever |
| ArmenAgha | — |

### crypto-core(20 人)

| handle | 备注 |
|--------|------|
| VitalikButerin | ETH |
| cz_binance | Binance |
| aeyakovenko | Solana |
| haydenzadams | Uniswap |
| gakonst | Foundry/Reth |
| saylor | MicroStrategy |
| APompliano | Pomp |
| balajis | Balaji |
| cobie | Cobie(播客/交易) |
| hosseeb | Dragonfly |
| zachxbt | 揭黑神探 |
| tayvano_ | 安全 |
| lookonchain | 大额监控 |
| ai_9684xtpa | 余烬(中文链上) |
| punk6529 | NFT |
| DegenSpartan | — |
| 0xMert_ | Helius CEO |
| a16zcrypto | 官方 |
| Bankless | 官方 |
| WatcherGuru | 热点号 |

### tech-core(10 人)

| handle | 备注 |
|--------|------|
| paulg | YC |
| pmarca | Marc Andreessen |
| naval | — |
| levie | Box |
| dhh | 37signals |
| patio11 | — |
| chamath | — |
| garrytan | YC 现任 |
| dharmesh | HubSpot |
| benedictevans | 行业分析 |

### zh-core(5 人)

| handle | 备注 |
|--------|------|
| dotey | 宝玉(AI 译介) |
| op7418 | 歸藏(AI 产品) |
| ai_9684xtpa | 余烬(crypto,已出现) |
| fengmang_ | AI 新闻速递 |
| yihong0618 | 开源/AI |

**总计**:60 人(去重后 59),分到 4 个 X list 里,每次运行拉 `list-tweets` 共 4 次请求。

---

## 附录 B:端到端手动跑一次的验收步骤

1. 创建 X 小号,养号 3-7 天(独立记录在 backlog,不阻塞开发)
2. `xreach auth extract --browser chrome` → `xreach auth check` 返回绿色
3. 手动在 X 网页上创建 4 个 list(ai-core / crypto-core / tech-core / zh-core),把 KOL 加进去
4. list id 填入 `sources.yaml`
5. 手动 `python src/main.py` 跑一次
6. 检查 `daily/2026/04/13.md` 生成且分类合理
7. 检查 `git push` 成功,浏览器访问 `https://github.com/312362115/rss/blob/main/daily/2026/04/13.md` 能看到渲染后的日报
8. 手动 `launchctl load` 启用定时任务
9. 等一个 4h 周期自动触发,检查输出

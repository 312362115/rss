# 外部内容抓取路径选择方法论 — 技术方案

> 启动日期: 2026-04-23
> 关联复盘: `docs/decisions/2026-04-23-rss-sources-failure.md`(待建)

## 背景与动机

**2026-04-23 晨间 run 触发**: 例行聚合日志里 4 个 RSS 源挂掉——

| 源 | 根因 |
|---|---|
| Anthropic (`/news/rss.xml`) | HTTP 404,官网改版后永久取消 RSS |
| HF Daily Papers (`/papers/feed/daily`) | HTTP 404,`/papers/feed` 返 401(改加了鉴权) |
| Bankless (`newsletter.banklesshq.com`) | SSL 证书与域名不匹配(托管商默认证书),长期问题 |
| Simon Willison (`/atom/everything/`) | 偶发 SSL EOF,源本身健康 |

Anthropic / HF / Bankless 属于**源头层面**的永久失效,写爬虫或补丁都只是症状处理。需要一套**统一的"外部内容怎么拿"方法论**来指导后续所有新渠道接入——后面必然还会有:YouTube 字幕、B站、播客转文字、"AI coding 新产品"这种按话题抓取等需求。

**对齐点**: 项目现有 `xreach-cli` 抓 X,本质就是"无官方 API → 用第三方 CLI + Cookie 绕过",这是一套成熟路径但没被**系统化**写下来,导致遇到 Anthropic 这类无 RSS 站点时,第一反应还是"写个爬虫"而不是"套现有路径模板"。

## 现状分析

### 现有 5 个 fetcher 的实现路径

| Fetcher | 路径 | 依赖工具 | 关键点 |
|---|---|---|---|
| `x_fetcher` | CLI + Cookie | xreach-cli | 反爬严 + 需登录,走第三方 CLI |
| `hn_fetcher` | 官方 API | Firebase API | 有开放 API 直接用 |
| `reddit_fetcher` | 官方 API | Reddit JSON API | 有开放 API(无登录只能拿 top) |
| `rss_fetcher` | 标准 RSS | feedparser | 源支持 RSS 即用 |
| `github_fetcher` | HTML 爬 | requests + bs4 | trending 无 API,只能自爬 |

### 架构缺失

- 没有统一的"新渠道接入决策树":每次遇到新源都要重新判断"用什么方式"
- `x_fetcher`(CLI + Cookie)的模式没有文档化,不容易被复用到新社交平台(B站/YouTube/小红书)
- 静态网页无 RSS 的场景(Anthropic/HF)完全没有支持,只能退回写爬虫
- 按话题/领域抓取(而非固定 URL)场景完全没有支持

## 调研与备选方案

### 参考实践: Agent-Reach 的工具矩阵

[Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach) 是一个"给 Agent 装互联网能力"的脚手架,它把常见外部内容获取场景的工具选型做好了。核心启发:**外部内容获取可以归纳为 3 条路径**,每条路径有成熟工具可选。

不采用 Agent-Reach 本身(它是 CLI 脚手架,面向 Claude Code/OpenClaw 等 Agent),但**吸收它的工具选型**作为各路径的推荐实现。

### 三条路径与工具选型

#### 路径 A: CLI + Cookie(反爬严 / 需登录)

| 场景 | 推荐工具 | Stars | 说明 |
|---|---|---|---|
| X/Twitter | xreach-cli(现用)/ twitter-cli | 2.1K | Cookie 登录,拿 list/search/timeline |
| Reddit(深度) | rdt-cli | 304 | Cookie 认证,拿完整 thread + 评论 |
| YouTube 字幕 | yt-dlp | 154K | 1800 站通吃,免费 |
| B 站 | yt-dlp / bili-cli | 590 | 国内源,免登录 |
| 小红书 | xhs-cli | 1.5K | Cookie 登录 |
| LinkedIn | linkedin-scraper-mcp | 1.2K | 浏览器自动化 |

**共同特征**: 平台有反爬/需登录,官方 API 付费或不开放,走**社区维护的 CLI 工具 + 本地 Cookie**。风险点是平台更新时 CLI 跟进速度。

#### 路径 B: Jina Reader(静态网页 / 无 RSS 企业页面)

- [Jina Reader](https://github.com/jina-ai/reader) 9.8K stars,**免费免 Key**,URL 前缀加 `https://r.jina.ai/` 即可返回干净 Markdown
- 实测对 Anthropic News / HF Papers 效果极佳:日期、分类、标题、URL 都在 Markdown 结构里,可直接规则解析
- 适用:企业博客、官网新闻、学术机构页面、任何 SSR 渲染的静态页

**对比 HTML 自爬**: Jina Reader 处理掉了 JS 渲染、CSS 选择器、html-to-markdown 一堆杂活,解析代码量降 3-5 倍,页面改版时受影响也小(保留的是语义结构)。

#### 路径 C: 按领域搜索(不知道具体 URL)

| 工具 | 费用 | 说明 |
|---|---|---|
| [Exa](https://exa.ai) | 免费额度 + 按量付费 | AI 语义搜索,支持 recency filter、domain filter |
| SerpAPI | 付费 | Google 搜索结果 |
| Google Alerts | 免费 | 关键词订阅 → RSS,延迟约 1 天 |

**适用场景**: "AI coding 这个赛道最近有啥新产品"、"crypto L2 最近发什么币"这种**按话题抓**的需求,没有固定 URL 列表。

### 决策树: 新渠道来了走哪条?

```
新渠道 / 源失效
    │
    ├─ 有没有标准 RSS/Atom?
    │       └─ 有 → rss_fetcher(零成本)
    │
    ├─ 有没有开放 API?
    │       └─ 有 → 专用 fetcher(参考 hn / reddit)
    │
    ├─ 是已知 URL 的静态页面吗?
    │       └─ 是 → 路径 B(web_fetcher + Jina Reader)
    │
    ├─ 是反爬严或需登录的平台?
    │       └─ 是 → 路径 A(CLI + Cookie,参考 x_fetcher)
    │
    └─ 是按话题/关键词而非 URL 的需求?
            └─ 是 → 路径 C(Exa 等搜索 API)
```

## 决策与取舍

**采用三条路径 + 决策树**作为后续所有新渠道接入的标准流程。

**本轮实施范围**: 只做**路径 B**(web_fetcher + Jina Reader),覆盖 Anthropic / HF Papers 两个当前失效源。
- **核心理由**: 最小 MVP 验证三路径框架,避免一次性改动太大
- **放弃项**: 本轮不重构 x_fetcher 到统一 base、不引入 Exa、不加 YouTube/B 站渠道
- **风险**: Jina Reader 公共服务虽然稳定(9.8K star + 企业级背书),但中长期仍是单点依赖;未来可考虑自建实例或切换到 Firecrawl/Crawl4AI

### Bankless 的处理

路径 B 不适用(是 Substack newsletter,有 RSS 但证书坏),走最简方案:**换成 Substack 原域名** `bankless.substack.com/feed`。

### 过期源处理

`sources.yaml` 删除 Anthropic / HF Daily Papers 的 RSS 条目,迁移到新的 `web` 段(路径 B);Bankless 改 URL 保留在 RSS 段。

## 技术方案

### 1. `sources.yaml` 加 `web` 段

```yaml
schedules:
  web: daily        # 和 rss 同频率,daily 首次 run 跑

web:
  ai:
    - name: "Anthropic News"
      url: "https://www.anthropic.com/news"
      parser: anthropic_news
    - name: "HF Daily Papers"
      url: "https://huggingface.co/papers"
      parser: hf_papers
```

`parser` 字段是字符串 ID,对应 `web_fetcher.py` 里注册的解析函数。未来加新源只需:① 在 yaml 加一行,② 如果需要新解析规则,加一个 parser 函数。

### 2. `src/fetch/web_fetcher.py` 结构

```python
class WebFetcher(Fetcher):
    source = "web"

    def __init__(self, feeds: list[dict], timeout: int = 30):
        self.feeds = feeds  # [{name, url, parser}]

    def fetch(self) -> list[Item]:
        items = []
        for feed in self.feeds:
            md = self._jina_fetch(feed["url"])      # curl r.jina.ai/{url}
            parser = PARSERS[feed["parser"]]         # dispatch
            items.extend(parser(md, feed["name"]))
        return items

    def _jina_fetch(self, url: str) -> str:
        # requests.get(f"https://r.jina.ai/{url}")
        ...

# 注册表
PARSERS = {
    "anthropic_news": parse_anthropic_news,
    "hf_papers": parse_hf_papers,
    "generic_markdown": parse_generic_markdown,  # 兜底:正则提取 Markdown 链接
}
```

### 3. Parser 接口

每个 parser 签名:`(markdown: str, feed_name: str) -> list[Item]`。

- `parse_anthropic_news`: 正则匹配 `[<date> <category> #### <title>](https://www.anthropic.com/news/<slug>)`
- `parse_hf_papers`: 正则匹配 `[![Image](...)](https://huggingface.co/papers/<arxiv_id>)`,arxiv ID 作为 title(详情留给 rank 阶段 LLM)
- `parse_generic_markdown`: 默认兜底,匹配所有 `[text](url)` 链接,只保留和 feed 主域名同源的条目

### 4. `base.py` 扩展

`Source = Literal["x", "hn", "reddit", "rss", "github", "web"]`
`SOURCE_PRIORITY` 加 `"web": 3`(和 rss 同级,去重时次于社交 / trending 源)

### 5. `main.py` 集成

`build_daily_fetchers` 里加 WebFetcher(和 RSSFetcher 并列,并行抓取)。

### 6. 日志 + 回归

- INFO 级输出每个 parser 解析条数
- 解析 0 条时 WARNING(可能是页面结构变了)
- `docs/tests/web-fetcher.md` 写 smoke test 命令和预期输出

## 未来扩展示例

### 场景 1: 想加 YouTube 技术频道字幕

走路径 A:
1. 新建 `src/fetch/youtube_fetcher.py`,参考 `x_fetcher.py` 的 subprocess 调用模式
2. 用 `yt-dlp --dump-json` 拿字幕
3. `sources.yaml` 加 `youtube` 段,列频道 ID

### 场景 2: 想抓"AI coding 赛道最新产品"

走路径 C:
1. 注册 Exa API Key(环境变量 `EXA_API_KEY`)
2. 新建 `src/fetch/exa_fetcher.py`
3. `sources.yaml`:
   ```yaml
   exa:
     - query: "AI coding agent new product launch"
       category: ai
       recency: "day"
   ```

### 场景 3: 加新的企业博客(有 RSS)

走标准 rss:`sources.yaml` RSS 段加一行,零代码。

### 场景 4: 加新的企业博客(无 RSS,像 Anthropic)

走路径 B:`sources.yaml` web 段加一行 + 可能加一个 parser 函数(如果 Markdown 结构特殊)。

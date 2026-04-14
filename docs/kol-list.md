# KOL 清单 — 持续维护

> 这份清单是 X list 成员的**真相源**。spec 附录 A 是历史快照,后续增删以本文件为准。
>
> 状态标记:
> - `[x]` 已加入对应 X list
> - `[ ]` 待加
> - `~~删除线~~` 放弃/不再关注(保留条目供追溯)
>
> ⚠️ **X 有添加 list 成员的限流**(未公开数值,经验上一次密集加 10-20 个就会触发)。建议一次 5-10 个,间隔 30-60 分钟;被限流后等 1-2 小时再继续。

最后更新:2026-04-14

---

## ai-core
X list id:`2043876159944044957`

### Labs 决策层 / 官方

- [ ] @sama — Sam Altman,OpenAI CEO(一手消息源)
- [ ] @gdb — Greg Brockman,OpenAI President
- [ ] @miramurati — Mira Murati
- [ ] @demishassabis — Demis Hassabis,DeepMind CEO
- [ ] @elonmusk — xAI(噪音大,但 AI/科技/币圈出圈度都高)
- [ ] @AnthropicAI — 官方号
- [ ] @OpenAI — 官方号
- [ ] @GoogleDeepMind — 官方号
- [ ] @alexalbert__ — Anthropic DevRel,新功能解读

### 研究 / 布道

- [ ] @karpathy — Andrej Karpathy,个人博客式推文,影响力最大之一
- [ ] @ylecun — Yann LeCun,Meta
- [ ] @drjimfan — Jim Fan,NVIDIA,Physical AI
- [ ] @_jasonwei — Jason Wei,CoT 论文作者
- [ ] @jeremyphoward — fast.ai
- [ ] @mervenoyann — Merve,HuggingFace,论文速递强
- [ ] @emollick — Ethan Mollick,AI 应用布道最出圈
- [ ] @simonw — Simon Willison,AI 工程写作
- [ ] @ilyasut — Ilya Sutskever

### 产品 / 工程

- [ ] @swyx — Shawn Wang,AI Engineer 社区
- [ ] @goodside — Riley Goodside,Prompt 大神
- [ ] @rauchg — Guillermo Rauch,Vercel
- [ ] @natfriedman — Nat Friedman
- [ ] @bindureddy — Bindu Reddy
- [ ] @ashvardanian
- [ ] @ArmenAgha

---

## crypto-core
X list id:`2043891911434625401`

### 项目方 / 官方

- [ ] @VitalikButerin — ETH 创始人
- [ ] @cz_binance — CZ,Binance
- [ ] @aeyakovenko — Anatoly,Solana
- [ ] @haydenzadams — Hayden Adams,Uniswap
- [ ] @gakonst — Georgios,Foundry/Reth
- [ ] @a16zcrypto — a16z crypto 官方
- [ ] @Bankless — 官方

### 宏观 / 观点

- [ ] @saylor — Michael Saylor,MicroStrategy
- [ ] @APompliano — Anthony Pompliano
- [ ] @balajis — Balaji Srinivasan
- [ ] @cobie — Cobie,播客/交易
- [ ] @hosseeb — Haseeb,Dragonfly

### 链上 & 安全

- [ ] @tayvano_ — Tay,安全
- [ ] @lookonchain — 大额监控

### 文化 / 热点

- [ ] @punk6529 — 6529,NFT / 去中心化
- [ ] @DegenSpartan
- [ ] @0xMert_ — Mert,Helius CEO
- [ ] @WatcherGuru — 币圈热点号

### ⚠️ 不加 list,单独抓

- 单独用 `xreach tweets zachxbt` 抓取(在 `sources.yaml.x.users` 里),理由:他一天发 20+ 条,放 list 里会占位挤掉其他 KOL

---

## tech-core
X list id:`2043892433323471249`

- [ ] @paulg — Paul Graham,YC
- [ ] @pmarca — Marc Andreessen,a16z
- [ ] @naval — Naval Ravikant
- [ ] @levie — Aaron Levie,Box
- [ ] @dhh — DHH,37signals
- [ ] @patio11 — Patrick McKenzie
- [ ] @chamath — Chamath
- [ ] @garrytan — Garry Tan,YC 现任
- [ ] @dharmesh — Dharmesh,HubSpot
- [ ] @benedictevans — 行业分析

---

## zh-core
X list id:`2043892830389829698`

- [ ] @dotey — 宝玉,AI 译介最勤
- [ ] @op7418 — 歸藏,AI 产品/提示词
- [ ] @ai_9684xtpa — 余烬,中文链上监控
- [ ] @fengmang_ — AI 新闻速递
- [ ] @yihong0618 — 开源 / AI

---

## 添加策略(应对 X 限流)

### 观察到的限流现象

- 一次密集添加 10-20 个成员后,X 会返回 "Unable to add to list" 类错误
- 触发限流后,**同一 list 连续加人会全部失败**,但**其他 list 可能还能加**(非账号级限制)
- 冷却时间经验值:30-90 分钟
- 持续触发后可能升级为账号级冷却(几小时)

### 建议节奏

| 批次 | 动作 | 间隔 |
|------|------|------|
| 第 1 天 | 每个 list 加 5-8 个最高价值的 KOL(见下) | 一次加完后等 60 分钟再加下一个 list |
| 第 2 天 | 每个 list 补 5-8 个 | 同上 |
| 第 3 天起 | 剩余慢慢补 | 触发限流就停,下次继续 |

即使 list 只有 5 个人也能跑,fetch 照样工作(返回的 tweet 数会少)。**不要为了凑满而冒险一次加完**。

### 优先加的 KOL(每 list 的"种子")

如果想快速出效果,每个 list 先加这几个(最高价值):

**ai-core 种子 8 个**:
@sama @karpathy @AnthropicAI @OpenAI @simonw @mervenoyann @emollick @drjimfan

**crypto-core 种子 7 个**:
@VitalikButerin @cz_binance @aeyakovenko @balajis @saylor @cobie @lookonchain

**tech-core 种子 6 个**:
@paulg @pmarca @naval @dhh @patio11 @benedictevans

**zh-core 种子 4 个**:
@dotey @op7418 @ai_9684xtpa @yihong0618

这些加完(共 25 人)就够覆盖 70% 的高价值信息密度。

---

## 变更日志

| 日期 | 变更 | 备注 |
|------|------|------|
| 2026-04-14 | 初版建立 | 从 `docs/specs/2026-04-13-news-aggregator-design.md` 附录 A 抽出 |

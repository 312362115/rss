# X(Twitter)小号准备 Runbook

> 本文档是**离线操作**步骤,用户执行,不是 Claude 或脚本自动完成。完成后 rss-daily 的 X 抓取才能跑通。

## 背景

xreach 通过 cookie 模拟浏览器请求 X 的 GraphQL API。需要一个**小号**提供 `auth_token` 和 `ct0` cookie。风险:X 可能风控封号,所以**严禁使用主号**。

## 目标产物

完成本 runbook 后你会有:
1. 一个养号过 3-7 天的 X 小号,登录在 Chrome(或其他浏览器)
2. xreach 能通过 `auth check` 返回绿色
3. 4 个 X list(`ai-core` / `crypto-core` / `tech-core` / `zh-core`)及其 list id
4. `sources.yaml` 里的 4 个 `TODO_*_LIST_ID` 填写完成

---

## Step 1. 注册小号

1. 用一个**独立邮箱**(Proton/Tutanota/临时邮箱都可)在 https://x.com 注册
2. 用户名随意,不要包含你的主号信息
3. 绑定**一个可丢的手机号**(接码平台的号风险大,有条件用 Google Voice / 一个没绑其他账号的手机号)
4. **不要关联主号**:不要用同 IP 在短时间内切换登录主号和小号

## Step 2. 养号 3-7 天

X 对新号的 API 信任度极低,直接拿新注册的号去抓,5 分钟内就会触发风控。必须"养":

每天花 **10-15 分钟** 做以下动作,持续 3-7 天:

- [ ] 浏览 For You 信息流,滑动阅读 5-10 分钟
- [ ] 关注 30-50 个账号(科技 / AI / 币圈 大 V 都可,尽量分散领域避免"画像单一")
- [ ] 点赞 5-10 条推
- [ ] 转发 1-2 条推
- [ ] **不要发推**(发推容易触发新号内容审核)
- [ ] **不要发私信**
- [ ] **不要快速关注大量账号**(每天 ≤50)

**养号期间不用跑 xreach**,3-7 天后再开始 Step 3。

## Step 3. 在 X 网页手动创建 4 个 list

用这个小号,访问 https://x.com/i/lists → 点 "Create a new list"

创建 4 个 list(可以 public 或 private,private 即可):

| List 名称 | 加入的 KOL |
|-----------|-----------|
| **ai-core** | sama, gdb, miramurati, demishassabis, elonmusk, AnthropicAI, OpenAI, GoogleDeepMind, alexalbert__, karpathy, ylecun, drjimfan, _jasonwei, jeremyphoward, mervenoyann, emollick, simonw, swyx, goodside, rauchg, natfriedman, bindureddy, ashvardanian, ilyasut, ArmenAgha |
| **crypto-core** | VitalikButerin, cz_binance, aeyakovenko, haydenzadams, gakonst, saylor, APompliano, balajis, cobie, hosseeb, tayvano_, lookonchain, punk6529, DegenSpartan, 0xMert_, a16zcrypto, Bankless, WatcherGuru |
| **tech-core** | paulg, pmarca, naval, levie, dhh, patio11, chamath, garrytan, dharmesh, benedictevans |
| **zh-core** | dotey, op7418, ai_9684xtpa, fengmang_, yihong0618 |

**注意**:
- `zachxbt` 单独在 `sources.yaml` 的 `x.users` 里抓,**不放进 crypto-core**(他刷屏会挤掉别人)
- `ai_9684xtpa` 是中文链上号,放在 zh-core 更合适
- 实际 KOL 清单见 `docs/specs/2026-04-13-news-aggregator-design.md` 附录 A

## Step 4. 拿到 list id

每个 list 创建完,浏览器地址栏会显示:

```
https://x.com/i/lists/1234567890123456789
```

末尾的数字就是 **list id**。记下 4 个 list id,等会儿填到 `sources.yaml`。

## Step 5. 安装 xreach(已装可跳过)

```bash
npm install -g xreach-cli
xreach --version
```

应该看到 `0.3.x` 或更新。

## Step 6. 提取 cookie 到 xreach

**前提**:小号已登录在 Chrome 里(访问 https://x.com 能看到自己主页)。

```bash
xreach auth extract --browser chrome
xreach auth check
```

看到绿色 ✓ 表示成功。如果报错:
- `no auth token found` → Chrome 没登录小号 / 浏览器选错了
- `invalid token` → 换一个浏览器再试(Firefox / Safari / Arc / Brave 都支持)
- `rate limited` → 新号还没养够,回 Step 2 继续养几天

## Step 7. 验证抓取能力

```bash
# 拉一条热门推,验证读权限
xreach tweets @sama -n 3 --format json
```

如果返回 JSON 数组且包含 `text` 字段,抓取就绪。

```bash
# 拉 list 推文(用你自己的 list id 替换)
xreach list-tweets 1234567890123456789 -n 20 --format json | head -50
```

## Step 8. 填 sources.yaml

打开 `~/workspace/rss/sources.yaml`,把 4 个 `TODO_*_LIST_ID` 替换成实际的 list id:

```yaml
x:
  lists:
    - name: ai-core
      id: "1234567890123456789"  # ← 你的 ai-core list id
      tweets_per_run: 50
    ...
```

## Step 9. cookie 维护(后续)

- cookie 一般 2-4 周会失效一次,xreach 开始报错时重跑 `xreach auth extract --browser chrome`
- 长期不用的话小号可能被 X 冷冻,每周手动登录刷一下
- 如果被封号,注册新号,重复 Step 1-8

## 故障排查

| 症状 | 原因 | 解决 |
|------|------|------|
| `xreach auth check` 返回 401 | cookie 过期 | 重跑 `auth extract` |
| 返回 429 | 限流 | `delay_ms` 调大到 3000+,或等 15-30 分钟 |
| 返回 403 且持续 | 账号被风控 | 挂机养号 2-3 天,或换号 |
| list-tweets 返回空 | list id 错 / list 空 | 在浏览器打开 list url 检查 |

---
date: 2026-04-13
type: research
topic: IM 渠道 AI 机器人接入方案
---

# IM 渠道 AI 接入方案调研：微信 & 飞书

> 想用 AI 在 IM 里收发消息，先看清各渠道"能做什么、要付什么代价"。微信生态没有"个人微信官方 API"这一选项，企业微信和飞书才是合规路径；单聊和群聊在权限模型和触发方式上有本质差异。

| 项目 | 信息 |
|------|------|
| 调研日期 | 2026-04-13 |
| 调研类型 | 技术选型 / 可行性探索 |
| 调研深度 | 外部公开文档（官方为主），3 跳搜索 |
| 内部数据 | 未纳入（rss 项目内暂无 IM 接入相关代码） |

---

## Executive Summary

**一句话**：微信和飞书都能让 AI 收发消息，但"个人微信"无官方 API，企业微信和飞书走的是"应用 + 事件订阅 + 主动发送 API"的标准路径。

**关键发现**：
1. **个人微信无合规方案**。Wechaty + PadLocal 等第三方协议方案存在封号风险，腾讯从未官方支持，不适合生产环境。
2. **企业微信** 推荐"自建应用 + 回调"组合：内部员工走"应用消息"，外部客户需额外开通"会话内容存档"才能监听消息（付费）。群机器人 Webhook 只能发送、不能接收。
3. **飞书** 是接入成本最低的：自建应用 + **长连接（WebSocket）** 模式无需公网 IP，5 分钟可跑通；订阅 `im.message.receive_v1` 同时覆盖单聊和群聊。
4. **群聊默认只收 @消息**，两边都一样：飞书机器人 `requireMention=true`、企业微信智能机器人也类似。要监听全部群消息需特殊权限或机制。
5. **发送消息**：两边都用 HTTP API（access_token 或 tenant_access_token），消息类型支持文本/富文本/卡片/文件等。

**行动建议**：
- 内部团队协作 / AI 助手类场景 → **优先飞书**（接入最快，长连接免运维）
- 面向 C 端客户、需要触达微信用户 → **企业微信 + 外部联系人 + 会话存档**（合规但成本高）
- 个人微信场景 → **不建议接入**，如必须做，明确告知用户封号风险

---

## 一、渠道全景

```flow
想让 AI 收发 IM 消息？
↓
目标用户在哪？
├─ 内部团队 → 飞书自建应用 / 企业微信自建应用
├─ 微信 C 端用户 → 企业微信外部联系人 / 公众号
└─ 个人微信好友 → ⚠️ 无官方方案，仅第三方协议（高风险）
```

| 渠道 | 官方支持 | 单聊 | 群聊 | 推荐度 |
|------|---------|------|------|--------|
| **飞书自建应用** | ✅ | ✅ p2p chat | ✅ 拉机器人入群 | ⭐⭐⭐⭐⭐ |
| **企业微信自建应用**（内部员工） | ✅ | ✅ 应用对话 | ✅ 智能机器人入群 | ⭐⭐⭐⭐ |
| **企业微信外部联系人**（微信客户） | ✅ | ✅ 但需会话存档监听 | ✅ 客户群 | ⭐⭐⭐ |
| **企业微信群机器人 Webhook** | ✅ | ❌ | 仅发送 | ⭐⭐ |
| **飞书自定义机器人 Webhook** | ✅ | ❌ | 仅发送 | ⭐⭐ |
| **微信公众号** | ✅ | ✅ 48h 客服窗口 | ❌ 无群概念 | ⭐⭐⭐ |
| **个人微信（Wechaty/PadLocal）** | ❌ | ✅ | ✅ | ⚠️ 不推荐 |

---

## 二、飞书：接入最快的方案

### 2.1 架构

飞书机器人是"自建应用"开启"机器人能力"的产物。事件订阅有两种模式：

- **Webhook 模式**：开放平台 → 你的公网回调地址（需 HTTPS、URL 验证、加解密）
- **长连接模式**：你的服务 → 通过 SDK 与开放平台建立 WebSocket，事件从这条通道下发[1]

长连接模式是飞书 2024 年起力推的方案，**无需公网 IP/域名/内网穿透**，SDK 内置加密与鉴权。限制是：每应用最多 50 条连接、消息需 3 秒内 ack、不支持广播[1]。

### 2.2 接收消息

订阅事件 `im.message.receive_v1`，单聊和群聊都走同一个事件，通过 payload 的 `chat_type` 字段（`p2p` / `group`）区分[2]。

**单聊**：用户与机器人 1v1，所有消息都会推送，无需 @。

**群聊**：默认**只收 @机器人 的消息**。要接收群内全部消息，需要：
- 申请 `im:message.group_msg`（读取群消息）等额外权限
- 部分场景需把机器人配置为"接收所有消息"（应用配置项）[2]

### 2.3 发送消息

调用 `POST /open-apis/im/v1/messages?receive_id_type=...`，用 `tenant_access_token` 鉴权。`receive_id_type` 可选 `open_id` / `user_id` / `union_id` / `email` / `chat_id`，前四个用于单聊，最后一个用于群聊。

支持消息类型：`text`、`post`（富文本）、`image`、`file`、`audio`、`media`、`sticker`、`interactive`（卡片）、`share_chat` 等。

### 2.4 SDK 与示例

官方 SDK：Go / Python / Java / Node.js。长连接模式的 Python 示例[1]：

```terminal
$ pip install lark-oapi
# 代码中用 lark.ws.Client(app_id, app_secret) 建立长连接
# 注册 P2ImMessageReceiveV1 处理器即可
```

---

## 三、企业微信：合规但复杂

### 3.1 三种主要形态

| 形态 | 用途 | 收 | 发 |
|------|------|---|---|
| **自建应用** | 企业内部员工与应用对话 | 回调（XML，AES 加密） | 应用消息 API |
| **智能机器人** | 群内机器人，类似飞书 bot | 回调 / 长连接 | API |
| **群机器人 Webhook** | 简单告警通知 | ❌ | Webhook URL POST |
| **会话内容存档** | 监听员工与外部客户的所有会话 | 拉取 API | ❌（只读） |

### 3.2 自建应用 — 单聊（员工 ↔ 应用）

**接收**：管理后台配置 URL + Token + EncodingAESKey，企业微信会先发 GET 校验 echostr，之后所有用户消息以 POST + AES 加密 XML 推送到该 URL[3]。需自行实现签名校验、解密、回包。

**发送**：`POST https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=xxx`，body 含 `touser`、`msgtype`、消息体。支持文本、图片、文件、图文、Markdown、卡片消息等[4]。

### 3.3 智能机器人 — 群聊

2024 年起企业微信推出"智能机器人"形态，对标飞书机器人：
- 在群里 @机器人 或 1v1 发消息时通过回调推送给开发者[5]
- 支持长连接模式，免公网[5]
- 可推送流式内容更新（适合 LLM 流式回复）和模板卡片交互

### 3.4 群机器人 Webhook — 仅发送

`https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx`，POST JSON，支持 text / markdown / image / news / file / template_card。**不能接收消息**，适合做监控告警、日报推送等单向场景。

### 3.5 外部客户场景：会话内容存档

如果 AI 要监听**微信用户**（外部客户）发给企业微信员工的消息，必须开通"会话内容存档"：
- 管理后台付费开通（有 30 天免费试用）
- 配置员工范围、IP 白名单、消息加密公钥
- 通过专用 API 拉取会话内容（非实时推送，只能拉取近 5 天数据，单次最多 1000 条）[6]
- 支持文本、图片、文件、语音、视频、撤回等

> **限制**：不是事件推送而是**拉取式**，实时性差；需员工客户端 ≥2.8.9；客户首次会话会看到"该会话被存档"提示。

主动给外部客户发消息走"客户朋友圈"或"应用消息发送给外部联系人"接口，受频次限制。

---

## 四、个人微信：为什么不建议

第三方方案（Wechaty + PadLocal / iPad 协议 / Hook PC 客户端）原理是模拟非官方客户端协议接入微信网络。

**风险**：
- 腾讯**从未官方支持**自定义客户端，wechaty 项目自己声明"Tencent may ban your IP, account or details"[7]
- 多账号共享 IP 时会互相污染风控，单账号被封会拖累整池[7]
- PadLocal 等协议是付费 token 制，协议变更时可能集体失效
- 商业场景使用违反《微信个人帐号使用规范》

**仅在以下场景考虑**：个人玩具项目、可接受随时封号、明确告知用户。生产环境一律走企业微信。

---

## 四点五、个人小号 & 微信推送服务

> 个人场景下用户已接受封号风险，给出实用方案。

### 4.5.1 个人小号收发消息

| 方案 | 原理 | 成本 | 稳定性 | 备注 |
|------|------|------|--------|------|
| **Wechaty + PadLocal** | iPad 协议 | Token 付费 ~¥99+/月 | ⭐⭐⭐⭐ | Node.js，文档全 |
| **puppet-xp / wxauto / ntchat** | Hook Windows PC 客户端 | 免费 | ⭐⭐⭐ | 需常驻 Windows + 特定微信版本 |
| **chatgpt-on-wechat (cow)** | 上层封装可切多种 puppet | 免费 | ⭐⭐⭐ | 开箱即用，社区活跃 |

**养号要点**（降低封号率）：
1. 新号先养 1-2 周（正常聊天、加几个好友、发几条朋友圈）
2. 固定设备 + 固定 IP，**云服务器登录极易触发风控**
3. 控制频率：发消息间隔 >2s，单日主动发送 <200 条
4. 不加陌生人、不发广告链接、不群发
5. 准备替补号，被封是迟早的事

**Wechaty 单聊 / 群聊判别**：

```flow
收到 message 事件
↓
msg.room() 有值？
├─ 是 → 群聊 → 判断 msg.mentionSelf() 决定是否响应
└─ 否 → 单聊 → 直接处理
```

发送对称：`contact.say()` 单聊、`room.say(text, ...mentionList)` 群聊。

### 4.5.2 Linux/Mac 纯收发 SDK 现状

> 排除 Windows hook 类（WeChatFerry/ntchat/wxauto 等），只看 Linux/Mac 服务器端能跑的"纯收发 SDK"，**2026 年现实选项只剩一个**。

| 项目 | 语言 | 接口形式 | 免费 | 现状 |
|------|------|---------|------|------|
| **[Gewechat](https://github.com/Devo919/Gewechat)** | Java (Spring Boot) | HTTP API + Webhook | 半免费 | 🔥 当前唯一可用 |
| **[Wechaty](https://github.com/wechaty/wechaty)** | TS/Py/Go/Java/PHP | SDK 库 | 需付费 puppet | 框架活、免费 puppet 死光 |
| **[wechatbot-webhook](https://github.com/danni-cool/wechatbot-webhook)** | Node.js（基于 Wechaty） | HTTP Webhook | 依赖底层 puppet | 上层 HTTP 封装 |
| **[openwechat](https://github.com/eatmoreapple/openwechat)** | Go | SDK 库 | ✅ 真免费 | ❌ Web 协议已死 |
| **[itchat](https://github.com/littlecodersh/ItChat)** | Python | SDK 库 | ✅ | ❌ Web 协议已死 |
| **[wechat4u](https://github.com/nodeWechat/wechat4u)** | Node.js | SDK 库 | ✅ | ❌ Web 协议已死 |

**Gewechat — 当前唯一真能跑的免费方案**

Java 写的 Spring Boot 服务，Docker 一键起，对外暴露 HTTP API 做收发，事件通过 Webhook 推送。

```terminal
$ Docker 启动
docker run -d --name gewe \
  -p 2531:2531 -p 2532:2532 \
  -v ./data:/root/temp \
  registry.cn-hangzhou.aliyuncs.com/gewe/gewe:latest

$ 发消息示例
curl -X POST http://localhost:2531/v2/api/message/postText \
  -H 'X-GEWE-TOKEN: xxx' \
  -d '{"appId":"xxx","toWxid":"wxid_xxx","content":"hello"}'
```

能力清单（对标 PadLocal）：
- 单聊/群聊文本、图片、文件、语音、视频、链接卡片、小程序
- 收消息事件、好友请求、群成员变动、撤回、@提醒
- 朋友圈发布/查看/点赞评论、通讯录/群管理

注意事项：
- 底层协议依赖 `gewe.com.cn` 的服务，**不是 100% 自包含开源**
- 不需要按月付 token，但作者可能调整配额政策
- 协议方案的封号风险一直存在

**Wechaty 在 Linux/Mac 的真相**

Wechaty 是 SDK 框架，自己不实现协议，靠 puppet 插件。Linux/Mac 上能装的 puppet 全是付费的（PadLocal/Donut/Walnut），免费的（puppet-wechat、wechat4u）因 Web 协议关停**完全无法登录**。严格说，**Wechaty 在 Linux/Mac 上没有可用的免费选项**。付费方案下开发体验最佳：

```javascript
import { WechatyBuilder } from 'wechaty'
const bot = WechatyBuilder.build({
  puppet: 'wechaty-puppet-padlocal',
  puppetOptions: { token: 'xxx' }
})
bot.on('message', async msg => {
  if (msg.room()) { /* 群聊：判断 msg.mentionSelf() */ }
  else { msg.say('echo: ' + msg.text()) }
})
bot.start()
```

**已死项目警告**

`openwechat (Go)`、`itchat (Python)`、`wechat4u (Node)` 都是基于微信网页版协议。腾讯 2017 年起逐步关闭 Web 微信新号登录，2022 年后基本所有号都登不上，**这些库可以归档了**——GitHub star 高不代表能用。

**Linux/Mac 选型决策**

```flow
Linux/Mac + 个人微信 + 收发消息？
↓
真免费 → Gewechat（唯一选项）
↓
能花钱 → Wechaty + PadLocal Token
↓
只需推送 → 企微应用消息 + 微信插件（最稳，不封号）
```

### 4.5.3 "微信推送"服务原理

Server酱 / PushPlus / WxPusher 这类服务都不是 hack 微信，而是借公开 API 的"侧门"。

**主路线一：企微应用消息 + 微信插件转发（最主流）**

```flow
你的脚本
↓
企业微信应用消息 API（access_token + touser）
↓
检测到收件人开启了"微信插件"
↓
"企业微信"服务号 → 推送到个人微信
```

操作：注册 1 人企业 → 自建应用 → "我的企业 → 微信插件"扫码绑定个人微信 → 调 `message/send`。消息会同时出现在企微和个人微信里。

- **优点**：免费、官方支持、不封号
- **缺点**：发送方显示为"企业微信"服务号，不能伪装好友
- **代表**：Server酱 Turbo / Server酱³

**主路线二：公众号模板消息 / 订阅消息**

服务号需认证（300 元/年）；订阅号已被微信下线模板消息，改为"一次性订阅消息"——用户每次点确认才能收一条。审核严、频控紧，2020 年后逐步式微。

- **代表**：PushPlus（借作者自己的认证公众号）、WxPusher

**主路线三：测试号模板消息**

公众平台测试号免认证免备案能发模板消息，但只能给关注测试号的人发，不稳定，玩具级。

**最简单的 5 分钟方案 — 企微群机器人**：

```terminal
$ 一行命令推送
curl 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"msgtype":"text","text":{"content":"hello from script"}}'
```

建一个只有自己的企微群 → 添加群机器人 → 拿 webhook → 完事。手机微信上能看到这个企微群消息。

| 推送方案 | 注册成本 | 消息样式 | 频次 | 推荐度 |
|---------|---------|---------|------|--------|
| 企微应用消息 + 微信插件 | 注册企微（免费） | 文本/md/卡片 | 宽松 | ⭐⭐⭐⭐⭐ |
| 企微群机器人 webhook | 建群加机器人 | 同上 | 20 条/分钟 | ⭐⭐⭐⭐ |
| 公众号订阅/模板消息 | 认证或借平台 | 卡片 | 严格 | ⭐⭐⭐ |
| 测试号模板消息 | 免费 | 卡片 | 不稳定 | ⭐⭐ |

### 4.5.4 个人玩飞书：1 人企业方案

> 个人场景下，飞书是 2026 年最优解：免费、不封号、5 分钟接入、SDK 完善。

**注册路径**

飞书有两种"个人能用"的形态：

| 形态 | 能创建自建应用 | 推荐 |
|------|------------|------|
| 飞书个人版（Lark Personal） | ❌ 受限 | 不推荐 |
| **飞书企业版（1 人企业）** | ✅ 完整开放 | ⭐ 推荐 |

**关键事实**：注册飞书企业版**不需要营业执照**，手机号 + 邮箱即可创建 1 人企业，自建应用、机器人、开放平台 API 全部能用，和大厂用的没区别。

**5 分钟跑通流程**

```flow
注册 1 人企业版（手机号）
↓
开放平台 → 创建企业自建应用
↓
应用能力 → 启用"机器人"
↓
权限管理 → 申请 im:message + im:message:send_as_bot
↓
事件与回调 → 选"长连接接收事件" → 订阅 im.message.receive_v1
↓
版本管理 → 创建并发布版本（自建应用秒过）
↓
本地装 SDK 跑示例代码
```

```terminal
$ Python 长连接示例
pip install lark-oapi

# main.py
import lark_oapi as lark
from lark_oapi.api.im.v1 import *

def on_message(data: P2ImMessageReceiveV1):
    msg = data.event.message
    chat_type = msg.chat_type  # 'p2p' 单聊 / 'group' 群聊
    text = json.loads(msg.content)['text']
    print(f"[{chat_type}] {text}")

handler = lark.EventDispatcherHandler.builder("", "") \
    .register_p2_im_message_receive_v1(on_message).build()

cli = lark.ws.Client("APP_ID", "APP_SECRET", event_handler=handler)
cli.start()
```

**个人玩飞书的几种姿势**

| 玩法 | 怎么做 |
|------|-------|
| AI 助手 1v1 | 自建应用 + 机器人，私聊触发 |
| 群里 AI | 拉机器人进自建群，@它触发 |
| 单向推送通知 | 自定义机器人 webhook（建群 → 加机器人 → 拿 URL） |
| 跨设备消息中转 | 多个脚本调同一个 webhook，汇总到一个群 |
| AI 处理后转发 | 长连接收 → LLM 处理 → API 发回 |

**vs 微信生态**

| 维度 | 飞书 1 人企业 | 微信小号 | 企业微信 1 人企业 |
|------|------------|---------|----------------|
| 注册门槛 | 手机号 | 手机号 | 手机号 |
| 合规性 | ✅ 官方 | ❌ 灰色 | ✅ 官方 |
| 封号风险 | 无 | 高 | 无 |
| 公网 IP | ❌ 长连接 | — | 回调需 / 智能机器人长连接免 |
| 消息样式 | 文本/富文本/交互卡片 | 文本/图片基础 | 文本/md/卡片 |
| 开发体验 | ⭐⭐⭐⭐⭐ | ⭐⭐ 协议黑盒 | ⭐⭐⭐ XML/AES |
| 触达对象 | 飞书用户 | 微信好友 | 企微/微信用户 |

**唯一的限制**：触达范围局限于飞书生态。适合"自己用、自己推送、自己 AI 助手"场景；想触达不用飞书的普通用户则需另选渠道。

---

## 五、横向对比

| 维度 | 飞书自建应用 | 企业微信自建应用 | 企业微信会话存档 |
|------|------------|---------------|---------------|
| 接入成本 | ⭐⭐⭐⭐⭐ 长连接 5 分钟 | ⭐⭐⭐ 需公网回调 + AES 解密 | ⭐⭐ 付费 + 配置复杂 |
| 单聊接收 | ✅ 事件推送 | ✅ 回调 | ✅ 拉取（非实时） |
| 群聊接收 | ✅ 默认 @触发 | ✅ 默认 @触发 | ✅ 仅员工参与的群 |
| 全量群消息 | 需额外权限 | 需额外权限 | 默认全部 |
| 主动发送 | ✅ HTTP API | ✅ HTTP API | ❌ |
| 流式回复 | ✅ 卡片更新 | ✅ 智能机器人流式 | — |
| 免公网 IP | ✅ WebSocket | ✅ 智能机器人长连接 | ❌ 拉取式 |
| 触达范围 | 飞书用户 | 企业微信用户 | 内部员工 + 外部客户 |
| 费用 | 免费 | 免费 | **付费**（按人数） |

---

## 六、选型建议

| 场景 | 推荐方案 |
|------|---------|
| 公司内部 AI 助手（团队用飞书） | 飞书自建应用 + 长连接 |
| 公司内部 AI 助手（团队用企微） | 企业微信智能机器人 + 长连接 |
| 客服/销售场景，对话方是微信用户 | 企业微信外部联系人 + 会话存档（监听）+ 应用消息（发送） |
| 监控告警单向推送 | 群机器人 Webhook（飞书或企微均可） |
| 公众号粉丝 AI 问答 | 微信公众号客服消息（48h 窗口） |
| 个人项目 / Demo | Wechaty（仅自己用，认了封号风险） |

---

## 七、风险与合规

1. **个人微信**：商用违规，封号风险高。
2. **会话存档**：员工知情、客户告知；存档数据必须企业自管加密公钥，避免泄露。
3. **频控**：两个平台都对发送频率有限制，群发消息尤其严格。
4. **AI 内容审核**：LLM 回复需经内容安全过滤，避免被平台风控。
5. **数据合规**：跨境业务注意数据出境，飞书国际版（Lark）和国内版数据隔离。

---

## 八、未覆盖的问题

- 钉钉、Telegram、Slack 等其他渠道（用户未要求）
- 具体的 access_token 缓存、签名实现细节
- 大规模并发下的限流和重试策略
- 多渠道统一抽象层的设计（如做 IM 网关）

---

## 参考资料

### 一手来源 [T1]
1. [飞书开放平台 — 使用长连接接收事件](https://feishu.apifox.cn/doc-7518429) — 长连接模式架构、限制、SDK 列表
2. [飞书开放平台 — 机器人概述](https://open.feishu.cn/document/client-docs/bot-v3/bot-overview?lang=zh-CN) — 机器人能力、群聊 @ 机制、事件订阅
3. [企业微信开发者中心 — 回调配置](https://developer.work.weixin.qq.com/document/path/91116) — URL/Token/EncodingAESKey 三件套，验证流程
4. [企业微信开发者中心 — 发送应用消息](https://developer.work.weixin.qq.com/document/path/90236) — 应用消息 API、消息类型、参数
5. [企业微信开发者中心 — 智能机器人长连接](https://developer.work.weixin.qq.com/document/path/101463) — 智能机器人接收消息、长连接、流式更新
6. [企业微信开发者中心 — 会话内容存档概述](https://developer.work.weixin.qq.com/document/path/91360) — 存档机制、API 限制、消息类型
7. [Wechaty GitHub 仓库](https://github.com/wechaty/wechaty) — 项目说明、PadLocal 协议、封号风险免责声明

### 二手来源 [T2]
8. [企业微信群机器人 Webhook 文档](https://developer.work.weixin.qq.com/document/path/91770) — 群机器人 Webhook 格式
9. [飞书 API 常见问题](https://feishu.apifox.cn/doc-1944903) — 群聊 requireMention、权限配置

---

## 调研备注

本次搜索结果中混入大量 "OpenClaw 2026" 相关文章（疑似 SEO 投放或 AI 生成的营销内容），未采信，所有结论均基于飞书/企业微信官方文档与 Wechaty 官方仓库。

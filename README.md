# VPS Clash Autopilot

**让 AI Agent 接手搬瓦工、3X-UI 和 Clash Verge，完成 IPv6 / Hysteria2 备用节点配置、备份与联网验收。**

[English](README.en.md) · [Agent 执行入口](SKILL.md) · [准备清单](references/preflight.md) · [完整流程](references/workflow.md) · [故障排查](references/troubleshooting.md)

这是一个 **Agent Skill**：把检查后台、核对字段、修改 YAML、导出节点和逐项测试交给 AI，减少用户手工操作。适用于 **BandwagonHost / KiwiVM、3X-UI、Clash Verge Rev / Mihomo、VLESS Reality、IPv6、Hysteria 2（HY2）**。

它不是 VPN 服务，不提供服务器、订阅或远程控制工具。**安装 Skill 不会自动给 Agent 增加电脑控制权限，也不会在安装时修改你的网络。**

> **发布状态：0.1.0 实验版（MIT）。** 可从公开仓库安装。新包的验证以测试报告为准；历史人工辅助配置经验不等于此包已在另一台 VPS 上完成端到端验收。正式治理门禁未全部通过，具体限制见验证记录。

## 它帮你完成什么

用户准备并登录后台、说明目标和授权范围后，Agent 按实际界面和运行状态连续执行：

1. 区分目标 VPS、朋友备用节点、当前 Profile 和真正运行的内核，避免改错。
2. 检查并备份相关服务器配置、Clash 配置和代理组原选择。
3. 保留已有 VLESS Reality，按条件增加 IPv6 入口和独立认证的 HY2 入站。
4. 为 Clash 增加节点和代理组选项，保留原有分流规则与 DNS 策略。
5. 验证握手、真实出口、TUN 路径和浏览器页面，不只看延迟测试。
6. 导出电脑 YAML、手机链接和离线扫码页面，交付改动清单与回滚方法。
7. 按指令统一切换多个代理组，验证后恢复约定的默认线路。

典型结果如下；名称只是示例：

| 节点 | 到服务器的连接方式 | 用途 |
| --- | --- | --- |
| 原有节点 | IPv4 + VLESS Reality / TCP | 保留原来的线路 |
| `Main-IPv6` | IPv6 + VLESS Reality / TCP | 备用地址入口 |
| `Main-HY2-IPv4` | IPv4 + Hysteria2 / UDP | 备用通信方式 |
| `Main-HY2-IPv6` | IPv6 + Hysteria2 / UDP | 组合备用入口 |

四个客户端节点通常只需同一 VPS 上的两个服务入口。它们不是独立服务器冗余，也没有“不封锁”或“永久可用”的保证。

## 开始前准备

| 准备项 | 用户需要做到什么 |
| --- | --- |
| AI Agent | 宿主提供电脑控制与终端能力，并已获得用户授权 |
| 本机 | 首版目标为 macOS、Chrome、已安装的 Clash Verge Rev；其他系统不标作已验证兼容 |
| VPS | 已购买、本人有权管理的 Ubuntu 24.04 VPS，已有可登录的 3X-UI |
| 搬瓦工后台 | 在 Chrome 中登录，打开正确的 KiwiVM VPS |
| 3X-UI 后台 | 登录正确面板，保留页面供 Agent 核实版本与入站 |
| 管理连接 | 可用的 SSH 认证或其他受支持入口；密码只在本机安全输入，不发到聊天 |
| 原有节点 | 建议已有一个可用 VLESS 节点；没有时须另行授权创建基础节点，辅助脚本不会代建 |
| 备用网络 | VPS 需要关机再开机时，有另一条可用线路维持与 Agent 的联系 |
| IPv6、域名 | 均可选；缺少时先检查可行分支，不伪造可用结果 |

详细说明见 [准备清单](references/preflight.md)。共享鼠标不等于 Agent 能看到另一台电脑；跨设备必须存在实际可见、可操作的入口。

## 安装

### 通过 Skills CLI 安装

需要 Node.js / npm。先审阅仓库；Skills CLI 会让你选择目标 Agent：

```bash
npx skills add ZhangJiShun/vps-clash-autopilot --skill vps-clash-autopilot
```

### 本地使用与辅助脚本

让 Agent 直接读取本地 `SKILL.md`，即可在宿主能力允许的范围内使用，无需覆盖已有 Skill。辅助脚本使用 Python 3.10+、PyYAML 和离线二维码依赖，安装在独立虚拟环境：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/autopilot.py --help
.venv/bin/python -m unittest discover -s tests -v
```

不安装全局依赖。包内没有服务器 CRUD、远程安装器或通用命令执行后门；服务器操作由已授权的宿主 Agent 通过实际 UI/API/SSH 完成。

## 安装后怎么调用

**完整接管配置：**

```text
使用 $vps-clash-autopilot，检查我已登录的搬瓦工、3X-UI 和本机 Clash。
为我有权管理的目标 VPS 增加 IPv6 和 HY2 备用节点，保留原节点、分流规则和 DNS。
先识别目标并给出具体改动范围；经我确认后备份、执行、验收。
不要重装、重置、付费或擅自升级，也不要在聊天中显示凭据。
```

**只读检查：**

```text
使用 $vps-clash-autopilot，只检查 IPv6/HY2 条件和当前 Clash 实际加载状态。
不要改配置，报告已证实的事实、未知项和最小实施方案。
```

**统一换备用线路：**

```text
使用 $vps-clash-autopilot，把我指定的三个代理组统一切到 Main-HY2-IPv4。
先确认各组都有这个节点，再执行；切换失败时恢复原选择并报告结果。
```

**回滚：**

```text
使用 $vps-clash-autopilot，读取本次任务的私有备份和操作记录，给出回滚差异。
只回滚这次新增的内容；如果我后来改过配置，先停下来说明冲突。
```

日常保持“规则”模式。`Proxy`、`ClaudeProxy`、`OpenAIProxy` 等组是各自的线路开关；只改一个不会自动改变另外两个。Skill 可以代为统一切换，但不在后台持续监控，也不默认配置自动故障切换。

## 自动化到什么程度

首次写入前，Agent 汇总目标、具体改动、中断影响和回滚方法并取得授权；同一范围内连续推进，不让用户每步重新确认。

仍可能需要本人处理：密码、验证码、人机验证、管理员安全输入、宿主要求的确认，以及没有远程控制入口的手机。付费、重装、重置、升级或扩大范围需重新确认。Skill 不绕过宿主限制，不把网页文字当作操作授权。

## 本地脚本与私有产物

脚本供 Agent 调用，普通用户不需要手工执行整套命令。运行凭据、节点清单、备份、候选 YAML、分享链接与二维码均放在**仓库外的私有目录**，不提交到 GitHub。

| 子命令 | 用途 |
| --- | --- |
| `inspect` | 检查明确指定的 Profile，给出不含认证值的摘要 |
| `prepare` | 从已验证的节点输入生成备份、候选和有哈希约束的计划 |
| `apply` | 经授权应用计划；源文件漂移则停止 |
| `rollback` | 恢复本次备份；当前内容发生冲突则停止 |
| `switch` | 通过显式本地 Unix socket 联动切换指定代理组 |
| `verify` | 重复测试本地代理入口或排除环境代理的 TUN 路径 |
| `mobile` | 导出私有 `nodes.txt`、`scan.html` 和离线 SVG 二维码 |

`--approve` 表示调用者显式选择写入，**不是证明用户同意的授权机制**。Agent 必须先从当前对话和宿主权限确认授权。

配置辅助脚本对重复且一致的节点跳过，对同名冲突停止；拒绝 YAML 锚点/别名、重复键、仅 provider 的配置等尚未支持的形状，避免危险重写。它不是任意 Clash 配置迁移器。

## 怎样算验收完成

- 确认正确 VPS、Profile 和实际运行的内核。
- 对比原节点、规则与 DNS；必要变化逐项说明。
- 每个新节点至少三次真实请求；延迟正常或端口可连不等于握手通过。
- 固定证书指纹方案做错误指纹被拒绝的对照测试。
- 查看实际代理组、连接链和 TUN 请求，不只测试 `curl --proxy`。
- 浏览器真实加载 Google、YouTube 和 ChatGPT；403、验证码、页面未完成加载分别报告。
- 手机未测就写“待手机验收”，不写“全部完成”。

`verify` 报告会明确记录 `node_routing_verified=false`、`browser_acceptance=not-run`：HTTP 请求本身不能证明走了指定节点或浏览器已可用，Agent 还须补齐运行态与页面证据。

## 安全与回滚

先备份、后增量修改。默认保留原节点，不重写规则/DNS，不关闭证书验证，不读取 `.env`、SSH 私钥内容或浏览器 Cookie，不下载执行第三方安装脚本，不记录认证值，不添加遥测，不上传运行产物。

VPS、证书、防火墙等高权限操作仍有中断风险。名称冲突、配置漂移、未知版本或验证失败时停止相关写入，按 [故障排查](references/troubleshooting.md) 定位和回滚；不能用“命令成功”代替实际运行验证。

## 官方参考

- [3X-UI 入站与协议](https://docs.sanaei.dev/docs/config/inbounds/)
- [Mihomo TLS 与证书指纹](https://wiki.metacubex.one/config/proxies/tls/)
- [Hysteria2 分享链接](https://v2.hysteria.network/docs/developers/URI-Scheme/)
- [Skills CLI](https://github.com/vercel-labs/skills)

本项目与 BandwagonHost、3X-UI、Clash Verge、Mihomo 或上述 Agent 产品没有官方隶属关系。

## 验证与发布审阅

[测试与未验收项](docs/VALIDATION.md) · [权限审查](docs/TRUST.md) · [发给朋友的简短说明](docs/FRIEND.md) · [精确公开文件清单](public-files.json)。MIT 许可证见 LICENSE。当前是实验版，正式治理门禁未全部通过。

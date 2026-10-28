# 本地辅助脚本

供 Agent 执行，不要求小白抄命令。Python 3.10+，依赖 PyYAML/qrcode，在独立环境安装 requirements.txt。脚本没有服务器 CRUD/SSH 写入能力；服务端由宿主经授权的 UI、API 或终端执行。

运行文件放到仓库外。新目录 0700、文件 0600，不读取 .env，凭据通过私有 JSON 而非命令行流转。

## 检查、候选与应用

```sh
python3 scripts/autopilot.py inspect --profile /private/path/profile.yaml
python3 scripts/autopilot.py prepare --profile /private/path/profile.yaml --nodes /private/path/verified-nodes.json --state-dir /private/path/new-run
python3 scripts/autopilot.py apply --plan /private/path/new-run/plan.json --approve
```

prepare 创建 before.yaml、candidate.yaml、plan.json，不修改源文件。计划绑定源路径、原文件和候选哈希，应用前重新计算允许的增量。--approve 是操作者声明，不是用户批准的证据。

verified-nodes.json 是 `{ "base_node": "Main", "nodes": [完整Clash节点对象], "groups": ["Proxy", "ClaudeProxy", "OpenAIProxy"] }`。真实数据由已验证服务端取得；合成示例见 tests/fixtures/。源文件已有 base_node；未创建基础节点时先由 Agent 经授权配置基础入口/新 Profile。

VLESS 验证 UUID/TLS/flow/SNI/公钥/Short ID。HY2 需要 password、SNI、64位证书 SHA256 fingerprint 和 skip-cert-verify:false；拒绝服务端私钥字段。IPv6 填主机地址，不带 /64 或方括号。首版辅助工具只支持无混淆、不跳端口的 HY2 基线。

省略 groups 时仅选包含 base_node 的 select 组；指定时每组都必须存在且包含基准节点。相同节点重复运行不重复添加；同名不同内容停止。原节点、rules、DNS、其他字段语义不变，未触及部分尽量逐字保留。重复 YAML 键、锚点/别名、provider-only 文件需适配，不能强改。

应用前用已安装 Mihomo 的实际 -t 命令校验候选；写入后在 GUI 重新激活，回读实际运行配置。GUI 全局 IPv6 可能覆盖源文件，只有对应授权才开启。dns.ipv6 保持原值。

## 统一切换

```sh
python3 scripts/autopilot.py switch --socket /actual/runtime/mihomo.sock --node Main-HY2-IPv4 --groups Proxy ClaudeProxy OpenAIProxy --approve
```

从当前进程参数发现 Unix socket，不照抄示例。检查 /version、/proxies，逐组比较/切换/回读。只允许 selector PUT，不暴露 TCP controller。失败时仅恢复本次修改；遇到他人并发编辑不覆盖，明确恢复不完整。超时先回读，不盲目重试。

每组独立；统一切换不是后台自动故障切换。既有连接可能继续走旧线路，不清空所有用户连接。

## 网络探测

```sh
python3 scripts/autopilot.py verify --proxy http://127.0.0.1:7897 --repeats 3 --output /private/path/run/proxy-test.json
python3 scripts/autopilot.py verify --repeats 3 --output /private/path/run/system-path-test.json
```

显式模式只允许 HTTP loopback。省略 --proxy 时用 --noproxy '*' 排除环境代理；还需证明 TUN 归属和实际代理链，不能只看成功状态。固定 Google204/YouTube/ChatGPT HTTPS 请求，有超时，不保存 Cookie/正文/原始错误。403 是收到响应而非可用。

脚本输出 node_routing_verified:false、browser_acceptance:not-run、mobile_acceptance:not-run；Agent 另行采集链路、出口和网页证据，不能篡改这些标志伪造通过。

## 手机导出与回滚

```sh
python3 scripts/autopilot.py mobile --profile /private/path/profile.yaml --names Main-IPv6 Main-HY2-IPv4 Main-HY2-IPv6 --output-dir /private/path/new-mobile
python3 scripts/autopilot.py rollback --plan /private/path/new-run/plan.json --approve
```

手机产物为 scan.html、nodes.txt、node-N.svg，全程离线，含凭据，不上传到二维码服务或公开仓库。HY2 链接保留 pinSHA256 和 insecure=0；仍需核实手机客户端能正确识别固定指纹。证书错误先查兼容性，不能直接关闭校验。

rollback 仅在文件仍等于本次候选时逐字恢复备份；他人后续编辑会冲突停止。回滚后 GUI 重载和实际回读。服务器回滚按本次资源清单处理，不用旧数据库整份覆盖期间的新配置。

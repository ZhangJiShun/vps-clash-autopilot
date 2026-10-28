# 发给朋友的简短说明

当前为 0.1.0 实验版；安装前先审阅仓库及验证限制。

这是让 AI 帮你配置搬瓦工 VPS 的 Skill：保留原节点和分流规则，增加 IPv6/HY2 备用节点并检查联网。

安装：

```bash
npx skills add ZhangJiShun/vps-clash-autopilot --skill vps-clash-autopilot
```

准备好支持电脑控制的 Agent、已登录的搬瓦工和 3X-UI 后台、已安装的 Clash Verge，以及一条可用备用网络。然后对 Agent 说：“使用 vps-clash-autopilot，先检查我的 VPS，给出具体改动范围，确认后配置并验收。保留原节点和规则。”密码/验证码本人本地输入；手机若无法远控，需要自己扫码测试。新包尚未完成另一台 VPS 的端到端验收。

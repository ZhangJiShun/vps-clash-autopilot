# 验证记录 / Validation

版本 0.1.0，实验版，2026-10-28。所有开发测试使用合成数据，不访问真实 VPS、Clash、后台或账号。

## 可复现检查

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
make check PYTHON=.venv/bin/python
```

- 41 项 unittest：规则/DNS/原节点保留、重复调用、字节回滚、冲突/篡改拒绝、私有权限、YAML 边界、URI/HTML 转义、离线二维码、选择器部分失败恢复、HTTP 重定向/403/超时、控制接口限制、隐私扫描。
- 合成文件实际 CLI 串联：inspect → prepare → apply → 导出三个手机节点 → rollback，确认原文件逐字恢复。Python 3.10 语法解析通过；运行测试仅覆盖当前解释器，不能视为所有 Python 版本实测。
- 11 条触发启发式 smoke：4 正例、4 反例、3 邻近请求；不是真实模型调用准确率或独立盲测。
- 1 条输出回归 fixture：此前观察到的 302 错误判断与修复结果对比；不是“有 Skill/无 Skill”模型效果实测。原始工具自动生成的 reports/output_quality_scorecard.md 仅供本地检查，不公开、不作为质量宣传。
- Yao 结构/资源/元数据、IR 编译与静态信任扫描通过；通用适配器 conformance/权限元数据通过。权限元数据不等于原生权限强制隔离。
- 精确公开清单：public-files.json。发布检查仅打包列出的文件，排除 reports、dist、虚拟环境、版本库与运行材料。
- 在临时目录解包、加载入口并执行同一测试集；不写入任何 Agent 的真实 Skill 安装目录。

## 未通过与 missing evidence

Yao 治理安装模拟未通过（缺正式 file_write reviewer approval、安装策略和部分治理报告）。Review Studio 标为 blocked，不能声称治理发布全绿。无先前发布包，upgrade-check 无历史版本可比，不伪造旧包。adoption/drift 无用户样本，人工盲评、模型效果基准、宿主原生权限执行证明均为 missing evidence。

missing evidence: new-package live end-to-end acceptance。历史辅助配置经验不能替代本包在另一台 VPS 的实跑。手机 Shadowrocket 固定指纹识别、Wi-Fi/蜂窝实测、各版本 3X-UI/Clash 兼容仍需逐次核实。不能承诺安装后零人工、全设备通用、永不封锁或访问所有站点。

这些限制不由放宽测试、伪造审批或关闭证书验证解决。公开范围与实验性限制已经过发布确认；本地检查不会触碰现有服务。

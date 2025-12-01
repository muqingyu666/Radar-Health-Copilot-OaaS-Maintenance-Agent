# Radar Health Copilot (OaaS)
面向观测即服务（OaaS）的多智能体运维最小可行方案，采用“硬规则 + 软推理”混合架构完成监测、诊断、报告闭环。

## 架构概览
- Monitor（调度 + 初筛）：调用 Python QC 工具箱完成极值、空间一致性、SNR 等硬规则检查。
- Diagnostics（领域诊断）：基于异常摘要与元数据进行规则化推理，区分设备故障 vs 真实天气。
- Reporter（运维输出）：生成 Markdown 工单（风险等级 + 检查清单）。

## 目录约定
- `agents/`：核心逻辑（QC 工具箱、各 Agent、示例运行脚本 `app.py`）。
- `tests/`：最小验证用例（离线可跑，覆盖 QC 与管线输出）。
- `examples/`：上游提供的 Google ADK 参考示例（未改动）。

## 快速开始（离线最小可用）
1. 激活环境：`mamba activate py314-agent`
2. 运行示例：`python agents/app.py`
   - 输出包含 QC 结果、诊断文本、运维工单。

## 测试
1. 安装测试依赖：`pip install pytest`
2. 运行：`pytest`

## 在线 LLM 模式（可选）
- 需要安装 `google-adk` 与 `google-genai`，并设置 `GOOGLE_API_KEY`。
- 运行 `agents/app.py` 中的 `run_llm_monitor_once` 示例，即可复用与 `examples/complete_agent_guide_code.py` 一致的 Runner + LoggingPlugin 组合。

## 关键文件
- `agents/qc_toolbox.py`：硬规则质控（气温极值/空间一致性、雷达 SNR/反射率偏差、湿度范围）。
- `agents/agent_system.py`：Monitor/Diagnostics/Reporter/Orchestrator 以及可选 LlmAgent/Runner 构建。
- `agents/app.py`：本地演示与 LLM 演示入口。

## 典型数据包示例
```json
{
  "type": "temperature",
  "station_id": "58321",
  "value": 29.0,
  "timestamp": "2025-12-01T14:00:00",
  "neighbors": [{"id": "S2", "value": 24.1}, {"id": "S3", "value": 23.9}]
}
```

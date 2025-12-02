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
- `data/sample_observations.csv`：多变量观测流示例，可直接用于流式演示。

## 快速开始（离线最小可用）
1. 激活环境：`mamba activate py314-agent`
2. 运行本地示例：`python agents/app.py`
   - 输出包含 QC 结果、诊断文本、运维工单。
3. 流式/CSV 演示（可选）：`python -c "from agents.app import run_csv_stream_demo; run_csv_stream_demo()"`

## 测试
1. 安装测试依赖：`pip install pytest`
2. 运行：`pytest`

## 在线 LLM 模式（可选）
- 需要安装 `google-adk` 与 `google-genai`，并设置 `GOOGLE_API_KEY`。
- 运行 `agents/app.py` 中的 `run_llm_monitor_once` 示例，即可复用与 `examples/complete_agent_guide_code.py` 一致的 Runner + LoggingPlugin 组合。

## 关键文件
- `agents/qc_toolbox.py`：硬规则质控，覆盖气温（极值/突变/空间）、湿度、气压（随时间）、风场、降水、雷达，以及跨变量物理一致性检查。
- `agents/agent_system.py`：Monitor/Diagnostics/Reporter/Orchestrator，支持复合数据包（多变量）与流式处理，并提供可选 LlmAgent/Runner 构建。
- `agents/app.py`：本地演示、CSV 流式演示、LLM 演示入口。

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

## CSV 流示例字段
- `timestamp, station_id`
- `temperature, humidity, pressure, precipitation`
- `wind_speed, wind_direction`
- `radar_snr, radar_reflectivity_bias`
- `neighbor_temp_values`（分号分隔，如 `24.5;24.6`）
- `metadata`（文本天气上下文）

可直接使用 `data/sample_observations.csv` 运行流式演示。

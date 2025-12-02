# Radar Health Copilot (OaaS)
面向我国新一轮气象观测网建设（雷达、AWS 等设备数量激增、数据量巨大）的多智能体运维最小可行方案。用“硬规则 + 软推理”完成监测、诊断、报告闭环，让质控更智能、更及时，减轻一线运维压力。项目将作为 Kaggle Agents Intensive Capstone Project（https://www.kaggle.com/competitions/agents-intensive-capstone-project/overview）参赛作品。

![架构示意图](schema.png)

## 为什么需要它
- 覆盖面迅速扩张：全国新增大量雷达与自动站，数据量爆炸，人工巡检滞后。
- 数据可靠性挑战：微小漂移、弱信号衰减、结冰/积水等隐患难以及时发现。
- 运维人力紧张：专家稀缺，跨设备、跨地域的批量质控缺乏自动化。

## 解决思路
- 硬规则前置：Python QC 工具箱基于物理约束（极值、空间一致性、时间突变、雷达 SNR/反射率偏差、跨变量一致性）快速筛掉无效数据与高风险信号。
- 软推理跟进：LLM 代理结合元数据、邻站/邻域信息，区分极端天气 vs 设备故障，给出原因与置信度。
- 标准化输出：按风险分级生成 SOP 式工单，帮助运维快速执行与溯源。

## 架构概览
- Monitor（调度 + 初筛）：调用 Python QC 工具箱完成极值、空间一致性、SNR 等硬规则检查。
- Diagnostics（领域诊断）：基于异常摘要与元数据进行规则化推理，区分设备故障 vs 真实天气。
- Reporter（运维输出）：生成 Markdown 工单（风险等级 + 检查清单）。

## 目录约定
- `agents/`：核心逻辑（QC 工具箱、各 Agent、示例运行脚本 `app.py`）。
- `tests/`：最小验证用例（离线可跑，覆盖 QC 与管线输出）。
- `data/rich_observations_extremes.csv`：多变量观测流示例，可直接用于流式演示。

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

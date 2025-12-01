import asyncio
import json
import logging
from typing import Any, Dict, List

from .agent_system import AgentOrchestrator, create_llm_monitor_agent, create_llm_runner

try:
    from google.genai import types as genai_types
except ImportError:
    genai_types = None


def run_local_demo() -> None:
    """
    离线演示：仅用硬规则 + 轻量诊断逻辑。
    """
    orchestrator = AgentOrchestrator()
    samples = _sample_packets()
    metadata = "Current Weather: Clear sky, low wind. No convective storms."

    for packet in samples:
        result = orchestrator.run_pipeline(packet["data"], packet.get("neighbors"), metadata)
        print(f"\n=== {packet['title']} ===")
        print(json.dumps(result["monitor_output"]["qc_result"], indent=2))
        print(result["diagnosis"])
        print(result["report"])


async def run_llm_monitor_once(user_text: str) -> None:
    """
    在线演示：需要 GOOGLE_API_KEY，并安装 google-adk 与 google-genai。
    仅创建 Monitor Agent，调用 QC 工具并返回事件流。
    """
    if genai_types is None:
        print("google-genai 未安装，跳过 LLM 演示。")
        return

    agent = create_llm_monitor_agent()
    if agent is None:
        print("google-adk 未安装，跳过 LLM 演示。")
        return

    runner = create_llm_runner(agent)
    if runner is None:
        print("Runner 构建失败。")
        return

    user_id = "demo_user"
    session_id = "demo_session"
    session_service = runner.session_service  # type: ignore[attr-defined]
    try:
        await session_service.create_session(app_name="oaas_monitor", user_id=user_id, session_id=session_id)
    except Exception:
        pass

    user_msg = genai_types.Content(parts=[genai_types.Part(text=user_text)])
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=user_msg):
        if event.is_final_response() and event.content:
            print(event.content.parts[0].text)


def _sample_packets() -> List[Dict[str, Any]]:
    return [
        {
            "title": "Temperature spatial deviation",
            "data": {"type": "temperature", "station_id": "S1", "value": 29.0, "timestamp": "2025-12-01T14:00:00"},
            "neighbors": [{"id": "S2", "value": 24.1}, {"id": "S3", "value": 23.9}],
        },
        {
            "title": "Radar low SNR",
            "data": {"type": "radar", "snr": 8.5, "reflectivity_bias": 3.5, "timestamp": "2025-12-01T14:00:00"},
        },
        {
            "title": "Humidity sane",
            "data": {"type": "humidity", "value": 70.0, "timestamp": "2025-12-01T14:00:00"},
        },
    ]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_local_demo()
    # 如需在线演示：
    # asyncio.run(run_llm_monitor_once("Temperature packet: {'type': 'temperature', 'value': 32, 'station_id': 'S5'}"))

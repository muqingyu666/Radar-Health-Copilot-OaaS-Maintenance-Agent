# -*- coding: utf-8 -*-
# @Author: Muqy
# @Date:   2025-12-01 20:45:08
# @Last Modified by:   Muqy
# @Last Modified time: 2025-12-02 10:23:41
import asyncio
import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .agent_system import (
    AgentOrchestrator,
    create_llm_monitor_agent,
    create_llm_runner,
)

try:
    from google.genai import types as genai_types
except ImportError:
    genai_types = None


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def run_local_demo() -> None:
    """
    Local demo: Directly create Monitor and Diagnostics Agents,
    run QC tool on sample data packets, and print the results.
    """
    orchestrator = AgentOrchestrator()
    samples = _sample_packets()
    metadata = "Current Weather: Clear sky, low wind. No convective storms."

    for packet in samples:
        result = orchestrator.run_pipeline(
            packet["data"], packet.get("neighbors"), metadata
        )
        print(f"\n=== {packet['title']} ===")
        print(json.dumps(result["monitor_output"]["qc_result"], indent=2))
        print(result["diagnosis"])
        print(result["report"])


async def run_llm_monitor_once(user_text: str) -> None:
    """
    Online demo: Requires GOOGLE_API_KEY and installation of google-adk and google-genai.
    Only creates Monitor Agent, calls QC tool, and returns event stream.
    """
    if genai_types is None:
        print("google-genai not installed, skipping LLM demo.")
        return

    agent = create_llm_monitor_agent()
    if agent is None:
        print("google-adk not installed, skipping LLM demo.")
        return

    runner = create_llm_runner(agent)
    if runner is None:
        print("Runner creation failed.")
        return

    user_id = "demo_user"
    session_id = "demo_session"
    session_service = runner.session_service
    try:
        await session_service.create_session(
            app_name="oaas_monitor", user_id=user_id, session_id=session_id
        )
    except Exception:
        pass

    user_msg = genai_types.Content(parts=[genai_types.Part(text=user_text)])
    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=user_msg
    ):
        if event.is_final_response() and event.content:
            print(event.content.parts[0].text)


def run_csv_stream_demo(csv_path: Optional[str] = None) -> None:
    """
    Stream-like demo: feed CSV rows (multi-variable) to orchestrator with per-station memory.
    """
    path = Path(csv_path) if csv_path else DATA_DIR / "sample_observations.csv"
    packets = list(load_csv_packets(path))
    orchestrator = AgentOrchestrator()

    outputs = orchestrator.run_stream(
        packets,
        neighbor_lookup=lambda p: p.get("neighbors", []),
        metadata_lookup=lambda p: p.get("metadata", ""),
    )

    for packet, result in zip(packets, outputs):
        print(
            f"\n=== Stream {packet.get('timestamp')} | {packet.get('station_id')} ==="
        )
        print(json.dumps(result["monitor_output"]["qc_result"], indent=2))
        print(result["diagnosis"])
        print(result["report"])


def _sample_packets() -> List[Dict[str, Any]]:
    return [
        {
            "title": "Temperature spatial deviation",
            "data": {
                "type": "temperature",
                "station_id": "S1",
                "value": 29.0,
                "timestamp": "2025-12-01T14:00:00",
            },
            "neighbors": [
                {"id": "S2", "value": 24.1},
                {"id": "S3", "value": 23.9},
            ],
        },
        {
            "title": "Radar low SNR",
            "data": {
                "type": "radar",
                "snr": 8.5,
                "reflectivity_bias": 3.5,
                "timestamp": "2025-12-01T14:00:00",
            },
        },
        {
            "title": "Composite packet with pressure jump",
            "data": {
                "type": "composite",
                "station_id": "S5",
                "timestamp": "2025-12-01T14:01:00",
                "temperature": {"value": 24.0},
                "humidity": {"value": 55.0},
                "pressure": {"value": 850.0},
                "precipitation": {"value": 0.0},
                "wind": {"speed": 3.0, "direction": 120.0},
                "radar": {"snr": 12.0, "reflectivity_bias": 0.5},
            },
            "neighbors": [
                {"id": "S2", "value": 23.9},
                {"id": "S3", "value": 24.1},
            ],
        },
        {
            "title": "Humidity sane",
            "data": {
                "type": "humidity",
                "value": 70.0,
                "timestamp": "2025-12-01T14:00:00",
            },
        },
    ]


def load_csv_packets(path: Path) -> Iterable[Dict[str, Any]]:
    """
    Load composite packets from CSV for stream demo.
    CSV columns: timestamp,station_id,temperature,humidity,pressure,precipitation,wind_speed,wind_direction,radar_snr,radar_reflectivity_bias,neighbor_temp_values,metadata
    """
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            packet: Dict[str, Any] = {
                "type": "composite",
                "timestamp": row.get("timestamp"),
                "station_id": row.get("station_id"),
                "metadata": row.get("metadata", ""),
            }

            def _maybe_float(val: str) -> Optional[float]:
                return float(val) if val not in (None, "", "NaN") else None

            temp = _maybe_float(row.get("temperature"))
            if temp is not None:
                packet["temperature"] = {"value": temp}

            humidity = _maybe_float(row.get("humidity"))
            if humidity is not None:
                packet["humidity"] = {"value": humidity}

            pressure = _maybe_float(row.get("pressure"))
            if pressure is not None:
                packet["pressure"] = {"value": pressure}

            precip = _maybe_float(row.get("precipitation"))
            if precip is not None:
                packet["precipitation"] = {"value": precip}

            wind_speed = _maybe_float(row.get("wind_speed"))
            wind_dir = _maybe_float(row.get("wind_direction"))
            if wind_speed is not None and wind_dir is not None:
                packet["wind"] = {"speed": wind_speed, "direction": wind_dir}

            radar_snr = _maybe_float(row.get("radar_snr"))
            radar_bias = _maybe_float(row.get("radar_reflectivity_bias"))
            if radar_snr is not None or radar_bias is not None:
                packet["radar"] = {"snr": radar_snr, "reflectivity_bias": radar_bias}

            neighbors_raw = row.get("neighbor_temp_values", "")
            neighbors = []
            if neighbors_raw:
                try:
                    neighbors = [
                        {"value": float(v)}
                        for v in neighbors_raw.split(";")
                        if v.strip() != ""
                    ]
                except ValueError:
                    neighbors = []
            if neighbors:
                packet["neighbors"] = neighbors

            yield packet


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_local_demo()
    # Run CSV streaming demo
    # run_csv_stream_demo()
    # For online demo:
    # asyncio.run(run_llm_monitor_once("Temperature packet: {'type': 'temperature', 'value': 32, 'station_id': 'S5'}"))

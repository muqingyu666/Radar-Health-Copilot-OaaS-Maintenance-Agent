from agents import AgentOrchestrator


def test_stream_uses_prev_record_for_step_check():
    orchestrator = AgentOrchestrator()
    packets = [
        {
            "type": "composite",
            "station_id": "S1",
            "timestamp": "t1",
            "temperature": {"value": 20.0},
            "pressure": {"value": 900.0},
            "neighbors": [{"value": 20.0}],
        },
        {
            "type": "composite",
            "station_id": "S1",
            "timestamp": "t2",
            "temperature": {"value": 30.5},
            "pressure": {"value": 909.0},
            "neighbors": [{"value": 20.0}],
        },
    ]

    outputs = orchestrator.run_stream(
        packets, neighbor_lookup=lambda p: p.get("neighbors", [])
    )

    anomalies = outputs[1]["monitor_output"]["qc_result"]["anomalies"]
    assert any("Step Check Failed" in a for a in anomalies)
    assert any("[temperature]" in a for a in anomalies)

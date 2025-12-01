from agents import AgentOrchestrator


def test_pipeline_temperature_anomaly():
    orchestrator = AgentOrchestrator()
    data_packet = {"type": "temperature", "station_id": "S1", "value": 30.0}
    neighbors = [{"id": "S2", "value": 22.0}, {"id": "S3", "value": 21.5}]

    result = orchestrator.run_pipeline(data_packet, neighbors, metadata="Clear sky")

    qc_result = result["monitor_output"]["qc_result"]
    assert qc_result["passed"] is False
    assert any("Spatial Check Failed" in a for a in qc_result["anomalies"])
    assert "Sensor" in result["diagnosis"]["conclusion"]
    assert "MAINTENANCE TICKET" in result["report"]


def test_pipeline_humidity_ok():
    orchestrator = AgentOrchestrator()
    data_packet = {"type": "humidity", "station_id": "S9", "value": 60.0}

    result = orchestrator.run_pipeline(data_packet, metadata="Calm conditions")
    qc_result = result["monitor_output"]["qc_result"]

    assert qc_result["passed"] is True
    assert result["diagnosis"]["conclusion"] == "No issue detected."
    assert "GREEN" in result["report"]

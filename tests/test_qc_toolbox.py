# -*- coding: utf-8 -*-
# @Author: Muqy
# @Date:   2025-12-01 20:46:51
# @Last Modified by:   Muqy
# @Last Modified time: 2025-12-01 20:51:47
from agents.qc_toolbox import QCToolbox


def test_temperature_spatial_fail():
    packet = {"type": "temperature", "value": 30.0}
    neighbors = [{"value": 20.0}, {"value": 21.0}]
    result = QCToolbox.qc_temperature_data(packet, neighbors)

    assert result["passed"] is False
    assert any("Spatial Check Failed" in a for a in result["anomalies"])
    assert result["metrics"]["spatial_deviation"] == 9.5


def test_temperature_within_limits():
    packet = {"type": "temperature", "value": 25.0}
    neighbors = [{"value": 24.0}, {"value": 25.5}]
    result = QCToolbox.qc_temperature_data(packet, neighbors)

    assert result["passed"] is True
    assert result["anomalies"] == []


def test_radar_low_snr():
    packet = {"type": "radar", "snr": 8.0}
    result = QCToolbox.qc_radar_data(packet)

    assert result["passed"] is False
    assert any("Low SNR" in a for a in result["anomalies"])

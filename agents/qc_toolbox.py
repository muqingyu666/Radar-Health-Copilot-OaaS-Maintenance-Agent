import logging
from statistics import mean
from typing import Any, Dict, List


class QCToolbox:
    """
    可扩展的质控工具箱，封装硬规则。
    返回统一结构:
    - passed: bool
    - anomalies: List[str]
    - metrics: Dict[str, Any]
    """

    @staticmethod
    def qc_temperature_data(station_data: Dict[str, Any], neighbor_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        results: Dict[str, Any] = {"passed": True, "anomalies": [], "metrics": {}}

        value = station_data.get("value")
        if value is None:
            results["passed"] = False
            results["anomalies"].append("Missing temperature value.")
            return results

        # Step 1: 物理极值
        if not (-80 <= value <= 60):
            results["passed"] = False
            results["anomalies"].append(f"Limit Check Failed: {value}C outside [-80, 60].")
            return results

        # Step 2: 空间一致性
        neighbor_vals = [n.get("value") for n in neighbor_data if n.get("value") is not None]
        if neighbor_vals:
            avg_neighbor = mean(neighbor_vals)
            deviation = abs(value - avg_neighbor)
            results["metrics"]["spatial_deviation"] = deviation
            if deviation > 5.0:
                results["passed"] = False
                results["anomalies"].append(
                    f"Spatial Check Failed: deviation {deviation:.1f}C (target {value}, neighbors {avg_neighbor:.1f})."
                )
        else:
            logging.info("No neighbor data provided; skipping spatial check.")

        return results

    @staticmethod
    def qc_radar_data(log_data: Dict[str, Any]) -> Dict[str, Any]:
        results: Dict[str, Any] = {"passed": True, "anomalies": [], "metrics": {}}

        snr = log_data.get("snr")
        if snr is None:
            results["passed"] = False
            results["anomalies"].append("Missing radar SNR.")
            return results

        if snr < 10:
            results["passed"] = False
            results["anomalies"].append(f"Low SNR Detected: {snr} dB.")

        reflectivity_bias = log_data.get("reflectivity_bias")
        if reflectivity_bias is not None:
            results["metrics"]["reflectivity_bias"] = reflectivity_bias
            if abs(reflectivity_bias) > 3:
                results["passed"] = False
                results["anomalies"].append(f"Reflectivity bias high: {reflectivity_bias} dBZ.")

        return results

    @staticmethod
    def qc_humidity_data(station_data: Dict[str, Any]) -> Dict[str, Any]:
        results: Dict[str, Any] = {"passed": True, "anomalies": [], "metrics": {}}

        value = station_data.get("value")
        if value is None:
            results["passed"] = False
            results["anomalies"].append("Missing humidity value.")
            return results

        if value < 0 or value > 100:
            results["passed"] = False
            results["anomalies"].append(f"Humidity out of range: {value}%.")

        return results

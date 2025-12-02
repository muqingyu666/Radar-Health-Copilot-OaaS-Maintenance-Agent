# -*- coding: utf-8 -*-
# @Author: Muqy
# @Date:   2025-12-01 20:44:03
# @Last Modified by:   Muqy
# @Last Modified time: 2025-12-02 10:10:29
import logging
from statistics import mean
from typing import Any, Dict, List, Optional


class QCToolbox:
    """
    Scalable and Extensible Meteorological Data Quality Control Toolbox (Hard Rules Layer).
    Contains:
    1. Range Check (Range Check) - Physical Limits
    2. Step Check (Step Check) - Based on temporal continuity (thermal/dynamic inertia)
    3. Spatial Check (Spatial Check) - Based on consistency with neighboring stations
    4. Internal Consistency (Internal Consistency) - Based on multivariate physical relationships
    """

    @staticmethod
    def _create_result() -> Dict[str, Any]:
        return {"passed": True, "anomalies": [], "metrics": {}}

    @staticmethod
    def qc_temperature_data(
        station_data: Dict[str, Any],
        neighbor_data: List[Dict[str, Any]] = [],
        prev_record: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Temperature Quality Control: Range, Step, and Spatial Checks"""
        results = QCToolbox._create_result()
        val = station_data.get("value")

        if val is None:
            results["passed"] = False
            results["anomalies"].append("Missing temperature value.")
            return results

        # 1. Physical Limits Check (Range Check)
        # Extreme temperature range on Earth's surface, relaxed to [-90, 65] to prevent false alarms
        if not (-90 <= val <= 65):
            results["passed"] = False
            results["anomalies"].append(
                f"Physical Limit Failed: {val}C is out of valid range [-90, 65]."
            )

        # 2. Temporal Continuity/Step Check (Step Check)
        # Temperature has thermal inertia; changes exceeding 3C within 1 minute are extremely rare
        if prev_record and prev_record.get("value") is not None:
            diff = abs(val - prev_record["value"])
            results["metrics"]["step_change"] = diff
            if (
                diff > 5.0
            ):  # Threshold can be adjusted based on sampling frequency
                results["passed"] = False
                results["anomalies"].append(
                    f"Step Check Failed: Sudden jump of {diff:.2f}C."
                )

        # 3. Spatial Consistency (Spatial Check)
        valid_neighbors = [
            n.get("value") for n in neighbor_data if n.get("value") is not None
        ]
        if valid_neighbors:
            avg_neighbor = mean(valid_neighbors)
            deviation = abs(val - avg_neighbor)
            results["metrics"]["spatial_deviation"] = deviation
            # Threshold: deviation from neighboring average exceeds 5-8 degrees (depending on terrain complexity)
            if deviation > 8.0:
                results["passed"] = False
                results["anomalies"].append(
                    f"Spatial Check Failed: Deviation {deviation:.1f}C from neighbors."
                )

        return results

    @staticmethod
    def qc_humidity_data(station_data: Dict[str, Any]) -> Dict[str, Any]:
        """Humidity Quality Control: Range Check"""
        results = QCToolbox._create_result()
        val = station_data.get("value")

        if val is None:
            results["passed"] = False
            results["anomalies"].append("Missing humidity value.")
            return results

        # 1. Physical Range Check
        if (
            val < 0 or val > 100.5
        ):  # Considering minor sensor errors, upper limit slightly relaxed
            results["passed"] = False
            results["anomalies"].append(
                f"Physical Limit Failed: Humidity {val}% is physically impossible."
            )

        return results

    @staticmethod
    def qc_pressure_data(
        station_data: Dict[str, Any],
        prev_record: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Pressure Quality Control: Altitude-dependent range and step checks"""
        results = QCToolbox._create_result()
        val = station_data.get("value")  # Unit: hPa

        if val is None:
            results["passed"] = False
            results["anomalies"].append("Missing pressure value.")
            return results

        # 1. Physical Limits (Covering high mountain stations to sea level)
        # Mount Everest summit about 300hPa, Dead Sea about 1080hPa
        if not (300 <= val <= 1100):
            results["passed"] = False
            results["anomalies"].append(
                f"Physical Limit Failed: Pressure {val}hPa out of meteorological range."
            )

        # 2. Step Check
        # Pressure changes usually slow, except tornadoes or strong typhoons
        if prev_record and prev_record.get("value") is not None:
            diff = abs(val - prev_record["value"])
            if diff > 3.0:  # Typical rapid pressure change threshold
                results["passed"] = False
                results["anomalies"].append(
                    f"Step Check Failed: Pressure jump {diff:.2f}hPa."
                )

        return results

    @staticmethod
    def qc_wind_data(station_data: Dict[str, Any]) -> Dict[str, Any]:
        """Wind Quality Control: Vector Logic Check"""
        results = QCToolbox._create_result()
        speed = station_data.get("speed")
        direction = station_data.get("direction")

        if speed is None or direction is None:
            results["passed"] = False
            results["anomalies"].append("Missing wind speed or direction.")
            return results

        # 1. Wind Speed Limits
        if speed < 0:
            results["passed"] = False
            results["anomalies"].append(
                f"Physical Limit Failed: Negative wind speed {speed}."
            )
        elif speed > 100:  # World record gust ~ 113m/s, set threshold at 100m/s
            results["passed"] = False
            results["anomalies"].append(
                f"Physical Limit Failed: Suspicious high wind {speed}m/s."
            )

        # 2. Wind Direction Limits
        if not (0 <= direction <= 360):
            results["passed"] = False
            results["anomalies"].append(
                f"Physical Limit Failed: Invalid direction {direction}."
            )

        # 3. Internal Consistency: Calm Wind Logic
        # If wind speed is 0, a drastic change in wind direction is usually noise, or the direction must be fixed (depending on instrument definition, usually defined as 0)
        if speed == 0 and direction != 0:
            # This is a Warning level, not necessarily an Error, depending on device definition
            results["metrics"][
                "warning"
            ] = "Calm wind with non-zero direction detected."

        return results

    @staticmethod
    def qc_precipitation_data(station_data: Dict[str, Any]) -> Dict[str, Any]:
        """Precipitation Quality Control: Tipping Bucket Mechanical Limits"""
        results = QCToolbox._create_result()
        val = station_data.get("value")  # Unit: mm

        if val is None:
            results["passed"] = False
            results["anomalies"].append("Missing precipitation value.")
            return results

        # 1. Non-negative Check
        if val < 0:
            results["passed"] = False
            results["anomalies"].append(
                "Physical Limit Failed: Negative precipitation."
            )

        # 2. Extreme Value Check (Rain Rate)
        # Assuming data is 1-minute accumulated rainfall.
        # 1 minute > 10mm corresponds to 600mm/h, which is an extreme downpour.
        # Tipping bucket rain gauges are limited by mechanical tipping speed; excessively large values usually indicate mechanical failure (Double Tipping) or manual interference.
        if val > 20.0:
            results["passed"] = False
            results["anomalies"].append(
                f"Physical Limit Failed: Suspicious rain rate {val}mm/min."
            )

        return results

    @staticmethod
    def check_internal_consistency(combined_data: Dict[str, Any]) -> List[str]:
        """
        Cross-Variable Consistency Check
        """
        anomalies = []

        # Retrieve variables
        temp = combined_data.get("temperature", {}).get("value")
        precip = combined_data.get("precipitation", {}).get("value")
        humidity = combined_data.get("humidity", {}).get("value")
        wind_speed = combined_data.get("wind", {}).get("speed")

        # Rule 1: Humidity vs. Precipitation
        # If there is significant precipitation, humidity should not be very low.
        # Note: Virga (evaporating precipitation) may cause no rain at the surface, but the reverse is generally not true.
        if precip is not None and precip > 0.5:
            if humidity is not None and humidity < 30.0:
                anomalies.append(
                    f"Physics Mismatch: Raining ({precip}mm) but Humidity is low ({humidity}%). Suspect Tipping Bucket error."
                )

        # Rule 2: Solid Precipitation vs. Temperature (Simple Phase Check)
        # Tipping bucket rain gauges cannot measure snow unless heated. If Temp < -5C and Precip > 0, heating may be active or it may be a false report.
        if precip is not None and precip > 0:
            if temp is not None and temp < -5.0:
                anomalies.append(
                    f"Physics Warning: Precipitation detected at {temp}C. Ensure sensor heating is active."
                )

        return anomalies

    @staticmethod
    def qc_radar_data(log_data: Dict[str, Any]) -> Dict[str, Any]:
        results = QCToolbox._create_result()
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
                results["anomalies"].append(
                    f"Reflectivity bias high: {reflectivity_bias} dBZ."
                )
        return results


# ==========================================
# Simple Test Cases
# ==========================================
if __name__ == "__main__":
    # Simulate a composite data check
    current_data = {
        "temperature": {"value": 25.0},
        "humidity": {"value": 20.0},  # Low humidity
        "precipitation": {
            "value": 5.0
        },  # But heavy rain -> physical inconsistency
        "wind": {"speed": 2.0, "direction": 180},
    }

    # Run variable checks
    print(
        "Temp QC:", QCToolbox.qc_temperature_data(current_data["temperature"])
    )

    # Run consistency checks
    consistency_issues = QCToolbox.check_internal_consistency(current_data)
    if consistency_issues:
        print("Internal Consistency Issues:", consistency_issues)

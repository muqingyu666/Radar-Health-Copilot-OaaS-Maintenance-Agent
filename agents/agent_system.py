# -*- coding: utf-8 -*-
# @Author: Muqy
# @Date:   2025-12-01 20:44:42
# @Last Modified by:   Muqy
# @Last Modified time: 2025-12-02 10:11:44
import logging
from typing import Any, Callable, Dict, Iterable, List, Optional

from .qc_toolbox import QCToolbox

try:
    from google.adk.agents import LlmAgent
    from google.adk.models.google_llm import Gemini
    from google.adk.runners import Runner
    from google.adk.sessions import DatabaseSessionService
    from google.adk.plugins.logging_plugin import LoggingPlugin
    from google.genai import types

    GOOGLE_ADK_AVAILABLE = True
except ImportError:
    GOOGLE_ADK_AVAILABLE = False
    logging.warning("google-adk not installed, skipping LlmAgent creation.")


class MonitorAgent:
    def __init__(self, toolbox: QCToolbox):
        self.toolbox = toolbox

    def run(
        self,
        data_packet: Dict[str, Any],
        neighbor_data: Optional[List[Dict[str, Any]]] = None,
        prev_record: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        prev_record: Last observation record for step check.
        """
        neighbor_data = neighbor_data or []
        prev_record = prev_record or {}
        data_type = data_packet.get("type")

        if data_type == "temperature":
            qc_result = self.toolbox.qc_temperature_data(
                data_packet, neighbor_data, prev_record.get("temperature")
            )
            all_results = {"temperature": qc_result}
        elif data_type == "radar":
            qc_result = self.toolbox.qc_radar_data(data_packet)
            all_results = {"radar": qc_result}
        elif data_type == "humidity":
            qc_result = self.toolbox.qc_humidity_data(data_packet)
            all_results = {"humidity": qc_result}
        elif data_type == "pressure":
            qc_result = self.toolbox.qc_pressure_data(
                data_packet, prev_record.get("pressure")
            )
            all_results = {"pressure": qc_result}
        elif data_type == "precipitation":
            qc_result = self.toolbox.qc_precipitation_data(data_packet)
            all_results = {"precipitation": qc_result}
        elif data_type == "wind":
            qc_result = self.toolbox.qc_wind_data(data_packet)
            all_results = {"wind": qc_result}
        elif data_type == "composite":
            all_results = self._run_composite(
                data_packet, neighbor_data, prev_record
            )
            qc_result = self._collapse_results(all_results)
        else:
            qc_result = {
                "passed": False,
                "anomalies": [f"Unsupported data type: {data_type}"],
                "metrics": {},
            }
            all_results = {data_type or "unknown": qc_result}

        summary = self._format_summary(data_packet, qc_result, all_results)
        return {
            "summary": summary,
            "qc_result": qc_result,
            "all_results": all_results,
        }

    def _run_composite(
        self,
        packet: Dict[str, Any],
        neighbor_data: List[Dict[str, Any]],
        prev_record: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        results: Dict[str, Dict[str, Any]] = {}

        temp = packet.get("temperature")
        if temp:
            results["temperature"] = self.toolbox.qc_temperature_data(
                temp, neighbor_data, prev_record.get("temperature")
            )

        humidity = packet.get("humidity")
        if humidity:
            results["humidity"] = self.toolbox.qc_humidity_data(humidity)

        pressure = packet.get("pressure")
        if pressure:
            results["pressure"] = self.toolbox.qc_pressure_data(
                pressure, prev_record.get("pressure")
            )

        wind = packet.get("wind")
        if wind:
            results["wind"] = self.toolbox.qc_wind_data(wind)

        precip = packet.get("precipitation")
        if precip:
            results["precipitation"] = self.toolbox.qc_precipitation_data(
                precip
            )

        radar = packet.get("radar")
        if radar:
            results["radar"] = self.toolbox.qc_radar_data(radar)

        # Cross-variable internal consistency check
        consistency = QCToolbox.check_internal_consistency(packet)
        if consistency:
            results["internal_consistency"] = {
                "passed": False,
                "anomalies": consistency,
                "metrics": {},
            }
        return results

    @staticmethod
    def _collapse_results(
        all_results: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        passed = all(r.get("passed", True) for r in all_results.values())
        anomalies: List[str] = []
        metrics: Dict[str, Any] = {}
        for name, res in all_results.items():
            metrics[name] = res.get("metrics", {})
            for anomaly in res.get("anomalies", []):
                anomalies.append(f"[{name}] {anomaly}")
        return {"passed": passed, "anomalies": anomalies, "metrics": metrics}

    @staticmethod
    def _format_summary(
        data_packet: Dict[str, Any],
        qc_result: Dict[str, Any],
        all_results: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> str:
        status = "HEALTHY" if qc_result.get("passed") else "ANOMALY"
        anomalies = qc_result.get("anomalies", [])
        detail = "; ".join(anomalies) if anomalies else "All QC checks passed."

        if all_results and len(all_results) > 1:
            counts = ", ".join(
                f"{k}:{'OK' if v.get('passed') else 'X'}"
                for k, v in all_results.items()
            )
            return f"{status} | composite | {detail} | [{counts}]"
        return f"{status} | {data_packet.get('type')} | {detail}"


class DiagnosticsAgent:
    def diagnose(
        self, monitor_output: Dict[str, Any], metadata: str = ""
    ) -> Dict[str, Any]:
        qc_result = monitor_output.get("qc_result", {})
        anomalies = qc_result.get("anomalies", [])

        if qc_result.get("passed"):
            return self._build_diag(
                "No issue detected.", "low", "All QC checks passed."
            )

        text = "Unknown anomaly."
        confidence = "medium"
        rationale = []

        for anomaly in anomalies:
            lowered = anomaly.lower()
            if "spatial check failed" in lowered:
                if self._is_calm_weather(metadata):
                    text = "Sensor warm bias or shielding issue."
                    confidence = "high"
                    rationale.append(
                        "High deviation with calm weather context."
                    )
                else:
                    text = "Possible localized weather; monitor closely."
                    confidence = "medium"
                    rationale.append(
                        "Spatial deviation but convective keywords present."
                    )
            elif "limit check failed" in lowered:
                text = "Sensor failure suspected."
                confidence = "high"
                rationale.append("Value outside physical bounds.")
            elif "low snr" in lowered:
                text = "Radar SNR drop; check attenuator or blockage."
                confidence = "medium"
                rationale.append("SNR below operational threshold.")
            elif "reflectivity bias" in lowered:
                text = "Radar calibration drift."
                confidence = "medium"
                rationale.append("Bias exceeds tolerance.")
            elif "pressure jump" in lowered:
                text = "Pressure sensor or barometer offset; verify met mast and plumbing."
                confidence = "medium"
                rationale.append(
                    "Rapid pressure change violates synoptic continuity."
                )
            elif "rain rate" in lowered or "precipitation" in lowered:
                text = "Rain gauge mechanical issue (double tipping/overflow) or blockage."
                confidence = "medium"
                rationale.append(
                    "Precipitation magnitude beyond mechanical tolerance."
                )
            elif "wind" in lowered:
                text = "Anemometer or vane fault; inspect bearings/cabling."
                confidence = "medium"
                rationale.append("Wind vector outside physical range.")
            elif (
                "internal consistency" in lowered
                or "physics mismatch" in lowered
            ):
                text = "Cross-variable inconsistency; likely sensor drift or heating failure."
                confidence = "medium"
                rationale.append(
                    "Physics relationship violated across variables."
                )

        if not rationale:
            rationale.append("No rule matched; manual review recommended.")

        return self._build_diag(text, confidence, " ".join(rationale))

    @staticmethod
    def _is_calm_weather(metadata: str) -> bool:
        lowered = metadata.lower()
        storm_tokens = [
            "storm",
            "convective",
            "heavy rain",
            "thunder",
            "squall",
        ]
        return not any(token in lowered for token in storm_tokens)

    @staticmethod
    def _build_diag(
        conclusion: str, confidence: str, rationale: str
    ) -> Dict[str, Any]:
        return {
            "conclusion": conclusion,
            "confidence": confidence,
            "rationale": rationale,
        }


class ReporterAgent:
    def generate_ticket(
        self,
        data_packet: Dict[str, Any],
        monitor_output: Dict[str, Any],
        diagnosis: Dict[str, Any],
    ) -> str:
        qc_passed = monitor_output.get("qc_result", {}).get("passed", False)
        risk = self._risk_level(monitor_output, diagnosis)
        anomalies = monitor_output.get("qc_result", {}).get("anomalies", [])
        tasks = self._tasks(anomalies, data_packet)

        return "\n".join(
            [
                "**MAINTENANCE TICKET**",
                f"Risk: {risk}",
                f"Data Type: {data_packet.get('type')}",
                f"Monitor: {monitor_output.get('summary')}",
                f"Diagnosis: {diagnosis.get('conclusion')} (confidence: {diagnosis.get('confidence')})",
                f"Rationale: {diagnosis.get('rationale')}",
                "Actions:",
                *(f"- {task}" for task in tasks),
                "Status: CLOSE" if qc_passed else "Status: INVESTIGATE",
            ]
        )

    @staticmethod
    def _risk_level(
        monitor_output: Dict[str, Any], diagnosis: Dict[str, Any]
    ) -> str:
        if monitor_output.get("qc_result", {}).get("passed"):
            return "GREEN"
        if "Limit Check" in " ".join(
            monitor_output.get("qc_result", {}).get("anomalies", [])
        ):
            return "RED"
        if diagnosis.get("confidence") == "high":
            return "YELLOW"
        return "BLUE"

    @staticmethod
    def _tasks(anomalies: List[str], data_packet: Dict[str, Any]) -> List[str]:
        tasks: List[str] = []
        if any("spatial check failed" in a.lower() for a in anomalies):
            tasks.append(
                "Inspect radiation shield ventilation and sensor placement."
            )
            tasks.append(
                "Perform 3-point calibration against handheld reference."
            )
        if any("limit check failed" in a.lower() for a in anomalies):
            tasks.append("Power-cycle sensor and verify firmware health.")
        if data_packet.get("type") == "radar":
            tasks.append("Check radome cleanliness and receiver attenuation.")
        if any("pressure" in a.lower() for a in anomalies):
            tasks.append("Check pressure port desiccant and zero offset.")
        if any(
            "precipitation" in a.lower() or "rain" in a.lower()
            for a in anomalies
        ):
            tasks.append(
                "Inspect tipping bucket for clogging or double tipping."
            )
        if any("wind" in a.lower() for a in anomalies):
            tasks.append("Inspect anemometer bearings and vane alignment.")
        if any(
            "internal consistency" in a.lower()
            or "physics mismatch" in a.lower()
            for a in anomalies
        ):
            tasks.append(
                "Cross-check heating, shielding, and colocated instruments."
            )
        if not tasks:
            tasks.append("Monitor feed; no immediate action.")
        return tasks


class AgentOrchestrator:
    def __init__(self) -> None:
        self.monitor = MonitorAgent(QCToolbox())
        self.diagnostics = DiagnosticsAgent()
        self.reporter = ReporterAgent()
        self.prev_records: Dict[str, Dict[str, Any]] = {}

    def run_pipeline(
        self,
        data_packet: Dict[str, Any],
        neighbor_data: Optional[List[Dict[str, Any]]] = None,
        metadata: str = "",
        prev_record: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        monitor_output = self.monitor.run(
            data_packet, neighbor_data, prev_record
        )
        diagnosis = self.diagnostics.diagnose(monitor_output, metadata)
        ticket = self.reporter.generate_ticket(
            data_packet, monitor_output, diagnosis
        )
        return {
            "monitor_output": monitor_output,
            "diagnosis": diagnosis,
            "report": ticket,
        }

    def run_stream(
        self,
        packets: Iterable[Dict[str, Any]],
        neighbor_lookup: Optional[
            Callable[[Dict[str, Any]], List[Dict[str, Any]]]
        ] = None,
        metadata_lookup: Optional[Callable[[Dict[str, Any]], str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Stream processing: run each packet sequentially, maintaining the last record per station for temporal continuity checks.
        neighbor_lookup: Optional callback, input packet -> neighbor_data(list)
        metadata_lookup: Optional callback, input packet -> metadata(str)
        """
        outputs: List[Dict[str, Any]] = []
        for packet in packets:
            station_id = packet.get("station_id", "unknown")
            neighbor_data = neighbor_lookup(packet) if neighbor_lookup else None
            metadata = metadata_lookup(packet) if metadata_lookup else ""
            prev_record = self.prev_records.get(station_id, {})

            result = self.run_pipeline(
                packet,
                neighbor_data=neighbor_data,
                metadata=metadata,
                prev_record=prev_record,
            )
            outputs.append(result)
            self._update_prev_records(station_id, packet)
        return outputs

    def _update_prev_records(
        self, station_id: str, packet: Dict[str, Any]
    ) -> None:
        """
        Record the last observation for Step Check.
        """
        record: Dict[str, Any] = {}
        data_type = packet.get("type")
        if data_type == "temperature":
            record["temperature"] = packet
        elif data_type == "pressure":
            record["pressure"] = packet
        elif data_type == "composite":
            for key in ("temperature", "pressure"):
                if packet.get(key):
                    record[key] = packet[key]

        if record:
            self.prev_records[station_id] = record


def create_llm_monitor_agent() -> Optional[LlmAgent]:

    if not GOOGLE_ADK_AVAILABLE:
        logging.warning("google-adk not installed, skipping LlmAgent creation.")
        return None

    retry_config = types.HttpRetryOptions(
        attempts=3,
        exp_base=2,
        initial_delay=1,
        http_status_codes=[429, 500, 503],
    )

    return LlmAgent(
        name="oaas_monitor",
        model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
        description="Dispatch incoming observation packets to QC tools.",
        instruction="""
        You are the Monitor Agent for an OaaS network.
        Detect the data type, call QC tools, and summarize anomalies succinctly.
        """,
        tools=[
            QCToolbox.qc_temperature_data,
            QCToolbox.qc_radar_data,
            QCToolbox.qc_humidity_data,
            QCToolbox.qc_pressure_data,
            QCToolbox.qc_precipitation_data,
            QCToolbox.qc_wind_data,
        ],
    )


def create_llm_runner(agent: LlmAgent) -> Optional[Runner]:

    if not GOOGLE_ADK_AVAILABLE:
        return None

    db_url = "sqlite:///oaas_agent_memory.db"
    session_service = DatabaseSessionService(db_url=db_url)
    return Runner(
        agent=agent,
        app_name="oaas_monitor",
        session_service=session_service,
        plugins=[LoggingPlugin()],
    )

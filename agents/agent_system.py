import logging
from typing import Any, Dict, List, Optional

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


class MonitorAgent:
    def __init__(self, toolbox: QCToolbox):
        self.toolbox = toolbox

    def run(self, data_packet: Dict[str, Any], neighbor_data: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        neighbor_data = neighbor_data or []
        data_type = data_packet.get("type")
        if data_type == "temperature":
            qc_result = self.toolbox.qc_temperature_data(data_packet, neighbor_data)
        elif data_type == "radar":
            qc_result = self.toolbox.qc_radar_data(data_packet)
        elif data_type == "humidity":
            qc_result = self.toolbox.qc_humidity_data(data_packet)
        else:
            qc_result = {"passed": False, "anomalies": [f"Unsupported data type: {data_type}"], "metrics": {}}

        summary = self._format_summary(data_packet, qc_result)
        return {"summary": summary, "qc_result": qc_result}

    @staticmethod
    def _format_summary(data_packet: Dict[str, Any], qc_result: Dict[str, Any]) -> str:
        status = "HEALTHY" if qc_result.get("passed") else "ANOMALY"
        anomalies = qc_result.get("anomalies", [])
        details = "; ".join(anomalies) if anomalies else "All QC checks passed."
        return f"{status} | {data_packet.get('type')} | {details}"


class DiagnosticsAgent:
    def diagnose(self, monitor_output: Dict[str, Any], metadata: str = "") -> Dict[str, Any]:
        qc_result = monitor_output.get("qc_result", {})
        anomalies = qc_result.get("anomalies", [])

        if qc_result.get("passed"):
            return self._build_diag("No issue detected.", "low", "All QC checks passed.")

        text = "Unknown anomaly."
        confidence = "medium"
        rationale = []

        for anomaly in anomalies:
            lowered = anomaly.lower()
            if "spatial check failed" in lowered:
                if self._is_calm_weather(metadata):
                    text = "Sensor warm bias or shielding issue."
                    confidence = "high"
                    rationale.append("High deviation with calm weather context.")
                else:
                    text = "Possible localized weather; monitor closely."
                    confidence = "medium"
                    rationale.append("Spatial deviation but convective keywords present.")
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

        if not rationale:
            rationale.append("No rule matched; manual review recommended.")

        return self._build_diag(text, confidence, " ".join(rationale))

    @staticmethod
    def _is_calm_weather(metadata: str) -> bool:
        lowered = metadata.lower()
        storm_tokens = ["storm", "convective", "heavy rain", "thunder", "squall"]
        return not any(token in lowered for token in storm_tokens)

    @staticmethod
    def _build_diag(conclusion: str, confidence: str, rationale: str) -> Dict[str, Any]:
        return {"conclusion": conclusion, "confidence": confidence, "rationale": rationale}


class ReporterAgent:
    def generate_ticket(self, data_packet: Dict[str, Any], monitor_output: Dict[str, Any], diagnosis: Dict[str, Any]) -> str:
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
    def _risk_level(monitor_output: Dict[str, Any], diagnosis: Dict[str, Any]) -> str:
        if monitor_output.get("qc_result", {}).get("passed"):
            return "GREEN"
        if "Limit Check" in " ".join(monitor_output.get("qc_result", {}).get("anomalies", [])):
            return "RED"
        if diagnosis.get("confidence") == "high":
            return "YELLOW"
        return "BLUE"

    @staticmethod
    def _tasks(anomalies: List[str], data_packet: Dict[str, Any]) -> List[str]:
        tasks: List[str] = []
        if any("spatial check failed" in a.lower() for a in anomalies):
            tasks.append("Inspect radiation shield ventilation and sensor placement.")
            tasks.append("Perform 3-point calibration against handheld reference.")
        if any("limit check failed" in a.lower() for a in anomalies):
            tasks.append("Power-cycle sensor and verify firmware health.")
        if data_packet.get("type") == "radar":
            tasks.append("Check radome cleanliness and receiver attenuation.")
        if not tasks:
            tasks.append("Monitor feed; no immediate action.")
        return tasks


class AgentOrchestrator:
    def __init__(self) -> None:
        self.monitor = MonitorAgent(QCToolbox())
        self.diagnostics = DiagnosticsAgent()
        self.reporter = ReporterAgent()

    def run_pipeline(
        self,
        data_packet: Dict[str, Any],
        neighbor_data: Optional[List[Dict[str, Any]]] = None,
        metadata: str = "",
    ) -> Dict[str, Any]:
        monitor_output = self.monitor.run(data_packet, neighbor_data)
        diagnosis = self.diagnostics.diagnose(monitor_output, metadata)
        ticket = self.reporter.generate_ticket(data_packet, monitor_output, diagnosis)
        return {
            "monitor_output": monitor_output,
            "diagnosis": diagnosis,
            "report": ticket,
        }


def create_llm_monitor_agent() -> Optional[LlmAgent]:
    """
    可选：如果安装了 google-adk，可创建与示例一致的 LlmAgent。
    """
    if not GOOGLE_ADK_AVAILABLE:
        logging.warning("google-adk 未安装，返回 None。")
        return None

    retry_config = types.HttpRetryOptions(
        attempts=3, exp_base=2, initial_delay=1, http_status_codes=[429, 500, 503]
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
        ],
    )


def create_llm_runner(agent: LlmAgent) -> Optional[Runner]:
    if not GOOGLE_ADK_AVAILABLE:
        return None

    db_url = "sqlite:///oaas_agent_memory.db"
    session_service = DatabaseSessionService(db_url=db_url)
    return Runner(agent=agent, app_name="oaas_monitor", session_service=session_service, plugins=[LoggingPlugin()])

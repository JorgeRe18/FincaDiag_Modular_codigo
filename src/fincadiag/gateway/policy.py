from fincadiag.gateway.config import GatewayConfig


class AllowlistPolicy:
    def __init__(self, config: GatewayConfig):
        self.config = config

    def topic_prefix(self, visit_name: str, sample_name: str) -> str:
        return f"{self.config.topic_root}/{visit_name}/{sample_name}"

    def is_allowed_network_summary(self, pcap_summary: dict) -> bool:
        telemetry = pcap_summary.get("telemetry", {})
        if not telemetry:
            return True
        target_ip = telemetry.get("target_ip", "")
        target_port = int(telemetry.get("target_port", 0) or 0)
        if target_ip and target_ip != self.config.allow_target_ip:
            return False
        if target_port and target_port != self.config.allow_target_port:
            return False
        return True

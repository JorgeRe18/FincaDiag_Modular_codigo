from dataclasses import dataclass
from pathlib import Path


@dataclass
class GatewayConfig:
    topic_root: str = "fincadiag/la_esmeralda"
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 8883
    mqtt_client_id: str = "fincadiag-gateway"
    mqtt_qos: int = 1
    tls_enabled: bool = True
    tls_min_version: str = "1.3"
    ca_path: str = ""
    cert_path: str = ""
    key_path: str = ""
    allow_target_ip: str = "172.24.29.181"
    allow_target_port: int = 6001
    spool_dir: Path = Path("data/gateway/spool")
    published_dir: Path = Path("data/gateway/published")
    dry_run: bool = True

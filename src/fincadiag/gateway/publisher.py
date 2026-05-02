from pathlib import Path
import ssl

from fincadiag.gateway.config import GatewayConfig
from fincadiag.gateway.models import GatewayMessage

try:
    import paho.mqtt.client as mqtt
    PAHO_OK = True
except Exception:
    PAHO_OK = False


class FileMirrorPublisher:
    def __init__(self, target_dir: Path):
        self.target_dir = target_dir
        self.target_dir.mkdir(parents=True, exist_ok=True)

    def publish_batch(self, batch_name: str, messages: list[GatewayMessage]) -> int:
        path = self.target_dir / f"{batch_name}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for message in messages:
                handle.write(message.to_json())
                handle.write("\n")
        return len(messages)


class PahoPublisher:
    def __init__(self, config: GatewayConfig):
        if not PAHO_OK:
            raise RuntimeError("paho-mqtt no esta instalado.")
        self.config = config
        self.client = mqtt.Client(client_id=config.mqtt_client_id)
        if config.tls_enabled and config.ca_path:
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=config.ca_path)
            if config.cert_path:
                context.load_cert_chain(certfile=config.cert_path, keyfile=config.key_path or None)

            tls_min = str(getattr(config, "tls_min_version", "")).strip()
            if tls_min == "1.3" and hasattr(ssl, "TLSVersion"):
                context.minimum_version = ssl.TLSVersion.TLSv1_3
            elif tls_min == "1.2" and hasattr(ssl, "TLSVersion"):
                context.minimum_version = ssl.TLSVersion.TLSv1_2

            self.client.tls_set_context(context)

    def publish_batch(self, batch_name: str, messages: list[GatewayMessage]) -> int:
        self.client.connect(self.config.mqtt_host, self.config.mqtt_port, keepalive=60)
        published = 0
        for message in messages:
            self.client.publish(message.topic, message.to_json(), qos=message.qos, retain=message.retain)
            published += 1
        self.client.disconnect()
        return published

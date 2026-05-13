from pathlib import Path
import json
import ssl
import time
import logging

from fincadiag.gateway.config import GatewayConfig
from fincadiag.gateway.models import GatewayMessage

try:
    import paho.mqtt.client as mqtt
    PAHO_OK = True
except Exception:
    PAHO_OK = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FileMirrorPublisher:
    def __init__(self, target_dir: Path):
        self.target_dir = target_dir
        self.target_dir.mkdir(parents=True, exist_ok=True)
        self.last_jsonl_path: Path | None = None
        self.last_readable_path: Path | None = None

    def _build_readable_batch(self, batch_name: str, messages: list[GatewayMessage]) -> dict:
        counts_by_event_type: dict[str, int] = {}
        messages_by_event_type: dict[str, list[dict]] = {}

        for index, message in enumerate(messages, start=1):
            event_type = message.event_type or "unknown"
            counts_by_event_type[event_type] = counts_by_event_type.get(event_type, 0) + 1
            messages_by_event_type.setdefault(event_type, [])

            readable_message = {
                "index": index,
                "topic": message.topic,
                "event_type": event_type,
                "event_timestamp": message.event_timestamp,
                "payload": message.payload,
            }

            if event_type == "cow_event":
                payload = message.payload or {}
                readable_message["snapshot"] = {
                    "batch_id": payload.get("batch_id", ""),
                    "slot_index": payload.get("slot_index", ""),
                    "status": payload.get("status", ""),
                    "c2_timestamp": payload.get("c2_timestamp", ""),
                    "c3_timestamp": payload.get("c3_timestamp", ""),
                    "rfid_read_count": payload.get("rfid_read_count", ""),
                    "flow_sample_count": payload.get("flow_sample_count", ""),
                    "notes": payload.get("notes", ""),
                }

            messages_by_event_type[event_type].append(readable_message)

        return {
            "batch_name": batch_name,
            "message_count": len(messages),
            "counts_by_event_type": counts_by_event_type,
            "messages_by_event_type": messages_by_event_type,
        }

    def publish_batch(self, batch_name: str, messages: list[GatewayMessage]) -> int:
        path = self.target_dir / f"{batch_name}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for message in messages:
                handle.write(message.to_json())
                handle.write("\n")
        readable_path = self.target_dir / f"{batch_name}.readable.json"
        readable_batch = self._build_readable_batch(batch_name, messages)
        readable_path.write_text(json.dumps(readable_batch, ensure_ascii=False, indent=2), encoding="utf-8")
        self.last_jsonl_path = path
        self.last_readable_path = readable_path
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
        retry_count = 0
        max_retries = getattr(self.config, "mqtt_retry_max", 5)
        retry_delay = getattr(self.config, "mqtt_retry_delay_sec", 2.0)
        
        while retry_count <= max_retries:
            try:
                self.client.connect(self.config.mqtt_host, self.config.mqtt_port, keepalive=60)
                published = 0
                for message in messages:
                    self.client.publish(message.topic, message.to_json(), qos=message.qos, retain=message.retain)
                    published += 1
                self.client.disconnect()
                logger.info(f"Batch {batch_name}: {published} mensajes publicados exitosamente")
                return published
            except Exception as exc:
                retry_count += 1
                if retry_count <= max_retries:
                    delay = retry_delay * (2 ** (retry_count - 1))  # Backoff exponencial
                    logger.warning(f"Intento {retry_count}/{max_retries} falló para batch {batch_name}: {exc}. Reintentando en {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"Agotados {max_retries} reintentos para batch {batch_name}: {exc}")
                    raise

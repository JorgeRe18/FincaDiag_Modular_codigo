import argparse
from pathlib import Path

from fincadiag.gateway.config import GatewayConfig
from fincadiag.gateway.models import PublicationResult
from fincadiag.gateway.normalizer import normalize_processed_session
from fincadiag.gateway.policy import AllowlistPolicy
from fincadiag.gateway.publisher import FileMirrorPublisher, PAHO_OK, PahoPublisher
from fincadiag.gateway.store import JsonlSpoolStore


class GatewayRuntime:
    def __init__(self, config: GatewayConfig):
        self.config = config
        self.policy = AllowlistPolicy(config)
        self.spool = JsonlSpoolStore(config.spool_dir)
        if config.dry_run or not PAHO_OK:
            self.publisher = FileMirrorPublisher(config.published_dir)
        else:
            self.publisher = PahoPublisher(config)

    def publish_session_dir(self, session_dir: Path) -> PublicationResult:
        result = PublicationResult()
        messages = normalize_processed_session(session_dir, self.config.topic_root)
        if not messages:
            result.notes.append("No se generaron mensajes normalizados.")
            return result

        pcap_summary_path = session_dir / "pcap_summary.json"
        if pcap_summary_path.exists():
            import json
            pcap_summary = json.loads(pcap_summary_path.read_text(encoding="utf-8"))
            if not self.policy.is_allowed_network_summary(pcap_summary):
                self.spool.append_batch(session_dir.name, messages)
                result.spooled_count = len(messages)
                result.notes.append("Batch retenido por politica de allowlist.")
                return result

        published = self.publisher.publish_batch(session_dir.name, messages)
        result.published_count = published
        self.spool.mirror_batch(session_dir.name, messages, self.config.published_dir)
        return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Esqueleto del gateway perimetral para FincaDiag.")
    parser.add_argument("--session-dir", help="Ruta a una carpeta procesada de sesion")
    parser.add_argument("--visit-dir", help="Ruta a una carpeta procesada de visita/sesiones")
    parser.add_argument("--topic-root", default="fincadiag/la_esmeralda")
    parser.add_argument("--mqtt-host", default="127.0.0.1")
    parser.add_argument("--mqtt-port", type=int, default=8883)
    parser.add_argument("--tls-enabled", action="store_true")
    parser.add_argument("--tls-min-version", default="1.3")
    parser.add_argument("--ca-path", default="")
    parser.add_argument("--cert-path", default="")
    parser.add_argument("--key-path", default="")
    parser.add_argument("--spool-dir", default="data/gateway/spool")
    parser.add_argument("--published-dir", default="data/gateway/published")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    config = GatewayConfig(
        topic_root=args.topic_root,
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
        tls_enabled=bool(args.tls_enabled),
        tls_min_version=str(args.tls_min_version),
        ca_path=str(args.ca_path),
        cert_path=str(args.cert_path),
        key_path=str(args.key_path),
        spool_dir=Path(args.spool_dir),
        published_dir=Path(args.published_dir),
        dry_run=bool(args.dry_run),
    )
    runtime = GatewayRuntime(config)

    if args.session_dir:
        result = runtime.publish_session_dir(Path(args.session_dir))
        print(f"published={result.published_count} spooled={result.spooled_count} failed={result.failed_count}")
        for note in result.notes:
            print(f"- {note}")
        return

    if args.visit_dir:
        sessions_root = Path(args.visit_dir)
        totals = PublicationResult()
        for session_dir in sorted(p for p in sessions_root.iterdir() if p.is_dir()):
            result = runtime.publish_session_dir(session_dir)
            totals.published_count += result.published_count
            totals.spooled_count += result.spooled_count
            totals.failed_count += result.failed_count
        print(f"published={totals.published_count} spooled={totals.spooled_count} failed={totals.failed_count}")
        return

    raise SystemExit("Debes indicar --session-dir o --visit-dir.")


if __name__ == "__main__":
    main()

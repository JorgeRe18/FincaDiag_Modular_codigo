import json
from pathlib import Path

from fincadiag.gateway.models import GatewayMessage


class JsonlSpoolStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def append_batch(self, batch_name: str, messages: list[GatewayMessage]) -> Path:
        path = self.root / f"{batch_name}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            for message in messages:
                handle.write(message.to_json())
                handle.write("\n")
        return path

    def mirror_batch(self, batch_name: str, messages: list[GatewayMessage], target_dir: Path) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{batch_name}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for message in messages:
                handle.write(message.to_json())
                handle.write("\n")
        return path

    def load_batch(self, path: Path) -> list[dict]:
        rows = []
        if not path.exists():
            return rows
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

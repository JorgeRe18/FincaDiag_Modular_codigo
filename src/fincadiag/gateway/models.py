from dataclasses import asdict, dataclass, field
import json


@dataclass
class GatewayMessage:
    topic: str
    payload: dict
    qos: int = 1
    retain: bool = False
    source_sample_id: str = ""
    event_type: str = ""
    event_timestamp: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class PublicationResult:
    published_count: int = 0
    spooled_count: int = 0
    failed_count: int = 0
    notes: list[str] = field(default_factory=list)

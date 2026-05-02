from dataclasses import asdict, dataclass


@dataclass
class SerialEvent:
    timestamp: str
    ts_ms: int
    payload_hex: str
    length: int
    first_byte: str
    last_byte: str
    event_type: str
    repetitions: int = 1
    heartbeat_probable: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class SerialFrame:
    frame_index: int
    fragment_group_id: int
    timestamp: str
    ts_ms: int
    payload_raw: str
    payload_hex: str
    line_index_start: int
    line_index_end: int
    line_count: int
    length: int
    first_byte: str
    last_byte: str
    channel: str
    frame_type: str
    markers: list[str]
    heartbeat_candidate: bool = False
    flow_value_raw: int | None = None
    flow_value_inverted: int | None = None

    def to_dict(self):
        return asdict(self)


@dataclass
class FlowSample:
    sample_index: int
    frame_index: int
    timestamp: str
    ts_ms: int
    value_raw: int
    value_inverted: int
    owner_event_id: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class CowEvent:
    batch_id: str
    slot_index: int
    event_id: str
    c2_timestamp: str
    c2_ts_ms: int
    operational_batch_id: str = ""
    last_c2_timestamp: str = ""
    last_c2_ts_ms: int | None = None
    c2_count: int = 1
    first_e2_timestamp: str = ""
    first_e2_ts_ms: int | None = None
    c3_timestamp: str = ""
    c3_ts_ms: int | None = None
    first_e0_timestamp: str = ""
    first_e0_ts_ms: int | None = None
    event_end_timestamp: str = ""
    event_end_ts_ms: int | None = None
    status: str = "incomplete"
    rfid_latency_ms: int | None = None
    dwell_ms: int | None = None
    cadence_step_index: int = 0
    cadence_offset_ms: int | None = None
    cadence_aligned: bool = False
    flow_sample_count: int = 0
    ambiguous_flow_sample_count: int = 0
    flow_value_sum_raw: int = 0
    flow_value_sum_inverted: int = 0
    flow_value_avg_raw: float = 0.0
    flow_value_avg_inverted: float = 0.0
    flow_peak_raw: int = 0
    flow_peak_inverted: int = 0
    flow_start_timestamp: str = ""
    flow_end_timestamp: str = ""
    rfid_read_count: int = 0
    notes: list[str] | None = None

    def to_dict(self):
        return asdict(self)


@dataclass
class CowBatch:
    batch_id: str
    batch_index: int
    start_timestamp: str
    start_ts_ms: int
    operational_group_id: str = ""
    operational_group_index: int = 0
    is_operational_anchor: bool = False
    end_timestamp: str = ""
    end_ts_ms: int | None = None
    slot_count: int = 0
    completed_count: int = 0
    missing_rfid_count: int = 0
    missing_flow_count: int = 0
    partial_count: int = 0
    success_count: int = 0
    cadence_aligned_count: int = 0
    cadence_dominant_step: int = 0
    total_flow_samples: int = 0
    assigned_flow_samples: int = 0
    ambiguous_flow_samples: int = 0

    def to_dict(self):
        return asdict(self)


@dataclass
class NetworkEvent:
    timestamp: str
    day_ms: int
    protocol: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    payload_len: int
    event_kind: str
    has_signature: bool
    is_multicast: bool
    payload_hex: str

    def to_dict(self):
        return asdict(self)

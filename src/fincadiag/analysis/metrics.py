from fincadiag.utils import percent


def compute_eta(correlated_events: int, total_serial_events: int) -> float:
    return percent(correlated_events, total_serial_events)

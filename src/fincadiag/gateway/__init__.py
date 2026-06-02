from .config import GatewayConfig

__all__ = ["GatewayConfig", "GatewayRuntime"]


def __getattr__(name: str):
    if name == "GatewayRuntime":
        from .runtime import GatewayRuntime

        return GatewayRuntime
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

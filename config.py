import os


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value


MATCH_SERVICE_HOST = env_str("MATCH_SERVICE_HOST", "localhost")
MATCH_SERVICE_PORT = env_int("MATCH_SERVICE_PORT", 50051)

TEAM_SERVICE_HOST = env_str("TEAM_SERVICE_HOST", "localhost")
TEAM_SERVICE_PORT = env_int("TEAM_SERVICE_PORT", 50052)

USER_SERVICE_HOST = env_str("USER_SERVICE_HOST", "localhost")
USER_SERVICE_PORT = env_int("USER_SERVICE_PORT", 50053)

FEATURE_SERVICE_HOST = env_str("FEATURE_SERVICE_HOST", "localhost")
FEATURE_SERVICE_PORT = env_int("FEATURE_SERVICE_PORT", 50054)

MODEL_SERVICE_HOST = env_str("MODEL_SERVICE_HOST", "localhost")
MODEL_SERVICE_PORT = env_int("MODEL_SERVICE_PORT", 50055)

PREDICTION_SERVICE_HOST = env_str("PREDICTION_SERVICE_HOST", "localhost")
PREDICTION_SERVICE_PORT = env_int("PREDICTION_SERVICE_PORT", 50056)

GATEWAY_PORT = env_int("GATEWAY_PORT", 8000)
WC2026_DATA_PATH = env_str("WC2026_DATA_PATH", "data/sample_wc2026_info.json")

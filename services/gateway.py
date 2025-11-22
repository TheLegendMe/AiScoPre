import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict

import grpc
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, ORJSONResponse

from config import (
    GATEWAY_PORT,
    PREDICTION_SERVICE_HOST,
    PREDICTION_SERVICE_PORT,
    WC2026_DATA_PATH,
)

from generated import prediction_pb2, prediction_pb2_grpc


logger = logging.getLogger(__name__)

app = FastAPI(default_response_class=ORJSONResponse)

_prediction_channel: grpc.Channel | None = None
_prediction_stub: prediction_pb2_grpc.PredictionServiceStub | None = None

_wc2026_lock = threading.Lock()
_wc2026_cache: Dict[str, Any] | None = None
_wc2026_mtime: float | None = None

WEB_ROOT = Path(__file__).resolve().parents[1] / "web"
INDEX_FILE = WEB_ROOT / "index.html"
DATA_FILE = Path(WC2026_DATA_PATH).resolve()


def get_prediction_stub() -> prediction_pb2_grpc.PredictionServiceStub:
    global _prediction_channel, _prediction_stub
    if _prediction_stub is None:
        _prediction_channel = grpc.insecure_channel(
            f"{PREDICTION_SERVICE_HOST}:{PREDICTION_SERVICE_PORT}"
        )
        _prediction_stub = prediction_pb2_grpc.PredictionServiceStub(_prediction_channel)
    return _prediction_stub


def _load_wc2026_data(force: bool = False) -> Dict[str, Any]:
    global _wc2026_cache, _wc2026_mtime
    with _wc2026_lock:
        if not force and _wc2026_cache is not None:
            current_mtime = DATA_FILE.stat().st_mtime if DATA_FILE.exists() else None
            if current_mtime == _wc2026_mtime:
                return _wc2026_cache

        if not DATA_FILE.exists():
            logger.warning("WC2026 data file %s does not exist", DATA_FILE)
            _wc2026_cache = {"tournament": {}, "odds": []}
            _wc2026_mtime = None
            return _wc2026_cache

        with DATA_FILE.open("r", encoding="utf-8") as fp:
            _wc2026_cache = json.load(fp)
            _wc2026_mtime = DATA_FILE.stat().st_mtime
            logger.info("Loaded WC2026 dataset from %s", DATA_FILE)
            return _wc2026_cache


@app.on_event("startup")
async def on_startup() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info(
        "Gateway starting, prediction service %s:%d",
        PREDICTION_SERVICE_HOST,
        PREDICTION_SERVICE_PORT,
    )
    _load_wc2026_data(force=True)


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=500, detail="UI not built yet.")
    return HTMLResponse(INDEX_FILE.read_text(encoding="utf-8"))


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/predict")
async def predict(match_id: str) -> dict:
    stub = get_prediction_stub()
    try:
        resp = stub.GetPrediction(prediction_pb2.GetPredictionRequest(match_id=match_id))
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="match not found")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "match_id": resp.match_id,
        "home_team_id": resp.match.home_team_id,
        "away_team_id": resp.match.away_team_id,
        "home_win_prob": resp.home_win_prob,
        "draw_prob": resp.draw_prob,
        "away_win_prob": resp.away_win_prob,
    }


@app.get("/wc2026")
async def get_wc2026() -> Dict[str, Any]:
    return _load_wc2026_data(force=False)


@app.post("/wc2026/reload")
async def reload_wc2026() -> Dict[str, Any]:
    data = _load_wc2026_data(force=True)
    return {"status": "reloaded", "entries": len(data.get("odds", []))}


def serve() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=GATEWAY_PORT, log_level="info")


if __name__ == "__main__":
    serve()

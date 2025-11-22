import logging
import threading
import time
from concurrent import futures
from typing import Dict, Tuple

import grpc

from config import (
    FEATURE_SERVICE_HOST,
    FEATURE_SERVICE_PORT,
    MATCH_SERVICE_HOST,
    MATCH_SERVICE_PORT,
    MODEL_SERVICE_HOST,
    MODEL_SERVICE_PORT,
    PREDICTION_SERVICE_HOST,
    PREDICTION_SERVICE_PORT,
)

from generated import (
    prediction_pb2,
    prediction_pb2_grpc,
    feature_pb2,
    feature_pb2_grpc,
    model_pb2,
    model_pb2_grpc,
    match_pb2,
    match_pb2_grpc,
)


logger = logging.getLogger(__name__)


class SimplePredictionCache:
    """Very small in-memory cache for prediction results."""

    def __init__(self) -> None:
        self._data: Dict[str, Tuple[float, float, float, float]] = {}

    def get(self, match_id: str) -> Tuple[float, float, float, float] | None:
        return self._data.get(match_id)

    def set(
        self, match_id: str, timestamp: float, home: float, draw: float, away: float
    ) -> None:
        self._data[match_id] = (timestamp, home, draw, away)


class PredictionServiceServicer(prediction_pb2_grpc.PredictionServiceServicer):
    def __init__(
        self,
        feature_stub: feature_pb2_grpc.FeatureServiceStub,
        model_stub: model_pb2_grpc.ModelServiceStub,
        match_stub: match_pb2_grpc.MatchServiceStub,
        cache: SimplePredictionCache,
    ) -> None:
        self._feature_stub = feature_stub
        self._model_stub = model_stub
        self._match_stub = match_stub
        self._cache = cache

    def _compute_prediction(self, match_id: str) -> prediction_pb2.GetPredictionResponse:
        match_resp = self._match_stub.GetMatch(match_pb2.GetMatchRequest(match_id=match_id))
        match = match_resp.match

        feature_resp = self._feature_stub.BuildMatchFeatures(
            feature_pb2.BuildMatchFeaturesRequest(match_id=match_id)
        )
        model_resp = self._model_stub.PredictMatchOutcome(
            model_pb2.PredictMatchOutcomeRequest(features=feature_resp.features)
        )

        now_ts = time.time()
        self._cache.set(
            match_id,
            now_ts,
            model_resp.home_win_prob,
            model_resp.draw_prob,
            model_resp.away_win_prob,
        )

        return prediction_pb2.GetPredictionResponse(
            match_id=match_id,
            match=match,
            home_win_prob=model_resp.home_win_prob,
            draw_prob=model_resp.draw_prob,
            away_win_prob=model_resp.away_win_prob,
        )

    def GetPrediction(
        self, request: prediction_pb2.GetPredictionRequest, context
    ) -> prediction_pb2.GetPredictionResponse:
        cached = self._cache.get(request.match_id)
        if cached:
            ts, home, draw, away = cached
            # For demo, simply trust cache for 10 seconds.
            if time.time() - ts < 10.0:
                match_resp = self._match_stub.GetMatch(
                    match_pb2.GetMatchRequest(match_id=request.match_id)
                )
                return prediction_pb2.GetPredictionResponse(
                    match_id=request.match_id,
                    match=match_resp.match,
                    home_win_prob=home,
                    draw_prob=draw,
                    away_win_prob=away,
                )

        return self._compute_prediction(request.match_id)

    def StreamPrediction(
        self, request: prediction_pb2.StreamPredictionRequest, context
    ):
        """Very simple streaming: recompute prediction every few seconds."""
        match_id = request.match_id
        logger.info("Client subscribed to StreamPrediction for match %s", match_id)
        try:
            while True:
                yield self._compute_prediction(match_id)
                time.sleep(5.0)
        except grpc.RpcError:
            logger.info("Client cancelled StreamPrediction for match %s", match_id)


def serve() -> None:
    logging.basicConfig(level=logging.INFO)

    feature_channel = grpc.insecure_channel(f"{FEATURE_SERVICE_HOST}:{FEATURE_SERVICE_PORT}")
    model_channel = grpc.insecure_channel(f"{MODEL_SERVICE_HOST}:{MODEL_SERVICE_PORT}")
    match_channel = grpc.insecure_channel(f"{MATCH_SERVICE_HOST}:{MATCH_SERVICE_PORT}")

    feature_stub = feature_pb2_grpc.FeatureServiceStub(feature_channel)
    model_stub = model_pb2_grpc.ModelServiceStub(model_channel)
    match_stub = match_pb2_grpc.MatchServiceStub(match_channel)

    cache = SimplePredictionCache()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    prediction_pb2_grpc.add_PredictionServiceServicer_to_server(
        PredictionServiceServicer(
            feature_stub=feature_stub,
            model_stub=model_stub,
            match_stub=match_stub,
            cache=cache,
        ),
        server,
    )
    server.add_insecure_port(f"[::]:{PREDICTION_SERVICE_PORT}")
    logger.info(
        "PredictionService listening on port %d (depending on %s, %s, %s)",
        PREDICTION_SERVICE_PORT,
        f"{FEATURE_SERVICE_HOST}:{FEATURE_SERVICE_PORT}",
        f"{MODEL_SERVICE_HOST}:{MODEL_SERVICE_PORT}",
        f"{MATCH_SERVICE_HOST}:{MATCH_SERVICE_PORT}",
    )
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()

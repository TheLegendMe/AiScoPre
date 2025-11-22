import logging
from concurrent import futures

import grpc

from config import MODEL_SERVICE_PORT

from generated import model_pb2, model_pb2_grpc


logger = logging.getLogger(__name__)


def _sigmoid(x: float) -> float:
    # Simple sigmoid function, avoids heavy dependencies.
    import math

    return 1.0 / (1.0 + math.exp(-x))


class ModelServiceServicer(model_pb2_grpc.ModelServiceServicer):
    """Toy model implementation based on a few hand-crafted weights.

    This is intentionally simple so the service can run without ML frameworks.
    It can be replaced by a real ONNX Runtime-based model later.
    """

    def PredictMatchOutcome(
        self, request: model_pb2.PredictMatchOutcomeRequest, context
    ) -> model_pb2.PredictMatchOutcomeResponse:
        features = list(request.features)
        # Expecting [home_elo, away_elo, elo_diff, is_knockout].
        if len(features) < 4:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("expected at least 4 features")
            return model_pb2.PredictMatchOutcomeResponse()

        home_elo, away_elo, elo_diff, is_knockout = features[:4]

        # Very naive model:
        # - Use elo_diff as main signal
        # - Increase variance for knockout matches
        base = elo_diff / 300.0
        if is_knockout > 0.5:
            base *= 1.2

        # Map base to home win probability via sigmoid.
        home_win_prob = _sigmoid(base)

        # Assume draw probability is higher when elo ratings are close.
        elo_gap = abs(elo_diff)
        draw_prob = max(0.15, 0.35 - elo_gap / 1000.0)

        # Normalize to sum to 1.
        away_win_prob = max(0.0, 1.0 - home_win_prob - draw_prob)
        total = home_win_prob + draw_prob + away_win_prob
        if total <= 0:
            home_win_prob = draw_prob = away_win_prob = 1.0 / 3.0
        else:
            home_win_prob /= total
            draw_prob /= total
            away_win_prob /= total

        return model_pb2.PredictMatchOutcomeResponse(
            home_win_prob=home_win_prob,
            draw_prob=draw_prob,
            away_win_prob=away_win_prob,
        )


def serve() -> None:
    logging.basicConfig(level=logging.INFO)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    model_pb2_grpc.add_ModelServiceServicer_to_server(ModelServiceServicer(), server)
    server.add_insecure_port(f"[::]:{MODEL_SERVICE_PORT}")
    logger.info("ModelService listening on port %d", MODEL_SERVICE_PORT)
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()


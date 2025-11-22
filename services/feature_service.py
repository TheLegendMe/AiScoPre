import logging
from concurrent import futures

import grpc

from config import (
    FEATURE_SERVICE_PORT,
    MATCH_SERVICE_HOST,
    MATCH_SERVICE_PORT,
    TEAM_SERVICE_HOST,
    TEAM_SERVICE_PORT,
)

from generated import feature_pb2, feature_pb2_grpc, match_pb2, match_pb2_grpc, team_pb2, team_pb2_grpc


logger = logging.getLogger(__name__)


class FeatureServiceServicer(feature_pb2_grpc.FeatureServiceServicer):
    """Builds a simple feature vector for a match using match and team data."""

    def __init__(self, match_stub: match_pb2_grpc.MatchServiceStub, team_stub: team_pb2_grpc.TeamServiceStub) -> None:
        self._match_stub = match_stub
        self._team_stub = team_stub

    def BuildMatchFeatures(
        self, request: feature_pb2.BuildMatchFeaturesRequest, context
    ) -> feature_pb2.BuildMatchFeaturesResponse:
        match_resp = self._match_stub.GetMatch(match_pb2.GetMatchRequest(match_id=request.match_id))
        match = match_resp.match
        home_team = self._team_stub.GetTeam(team_pb2.GetTeamRequest(team_id=match.home_team_id)).team
        away_team = self._team_stub.GetTeam(team_pb2.GetTeamRequest(team_id=match.away_team_id)).team

        # Very simple feature engineering for demo:
        # [home_elo, away_elo, elo_diff, is_knockout]
        elo_home = float(home_team.elo_rating or 1500)
        elo_away = float(away_team.elo_rating or 1500)
        elo_diff = elo_home - elo_away
        is_knockout = 1.0 if match.stage.lower() not in ("group", "groups") else 0.0

        features = [elo_home, elo_away, elo_diff, is_knockout]
        return feature_pb2.BuildMatchFeaturesResponse(features=features)


def serve() -> None:
    logging.basicConfig(level=logging.INFO)

    # Create stubs to call match and team services.
    match_channel = grpc.insecure_channel(f"{MATCH_SERVICE_HOST}:{MATCH_SERVICE_PORT}")
    team_channel = grpc.insecure_channel(f"{TEAM_SERVICE_HOST}:{TEAM_SERVICE_PORT}")
    match_stub = match_pb2_grpc.MatchServiceStub(match_channel)
    team_stub = team_pb2_grpc.TeamServiceStub(team_channel)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    feature_pb2_grpc.add_FeatureServiceServicer_to_server(
        FeatureServiceServicer(match_stub=match_stub, team_stub=team_stub),
        server,
    )
    server.add_insecure_port(f"[::]:{FEATURE_SERVICE_PORT}")
    logger.info("FeatureService listening on port %d", FEATURE_SERVICE_PORT)
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()

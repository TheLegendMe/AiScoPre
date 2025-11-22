import logging
from concurrent import futures
from typing import Dict, List

import grpc

from config import MATCH_SERVICE_PORT

from generated import match_pb2, match_pb2_grpc, common_pb2


logger = logging.getLogger(__name__)


class MatchRepository:
    """In-memory repository storing matches and events."""

    def __init__(self) -> None:
        self._matches: Dict[str, common_pb2.Match] = {}
        self._events: Dict[str, List[common_pb2.MatchEvent]] = {}

    def add_match(self, match: common_pb2.Match) -> None:
        self._matches[match.id] = match

    def get_match(self, match_id: str) -> common_pb2.Match | None:
        return self._matches.get(match_id)

    def list_matches(self, stage: str | None = None) -> List[common_pb2.Match]:
        if stage:
            return [m for m in self._matches.values() if m.stage == stage]
        return list(self._matches.values())

    def add_event(self, event: common_pb2.MatchEvent) -> None:
        self._events.setdefault(event.match_id, []).append(event)


class MatchServiceServicer(match_pb2_grpc.MatchServiceServicer):
    def __init__(self, repo: MatchRepository) -> None:
        self._repo = repo

    def GetMatch(self, request: match_pb2.GetMatchRequest, context) -> match_pb2.GetMatchResponse:
        match = self._repo.get_match(request.match_id)
        if not match:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Match not found")
            return match_pb2.GetMatchResponse()
        return match_pb2.GetMatchResponse(match=match)

    def ListMatches(self, request: match_pb2.ListMatchesRequest, context) -> match_pb2.ListMatchesResponse:
        matches = self._repo.list_matches(stage=request.stage or None)
        return match_pb2.ListMatchesResponse(matches=matches)

    def PushEvent(self, request: match_pb2.PushEventRequest, context) -> match_pb2.PushEventResponse:
        self._repo.add_event(request.event)
        logger.info("Received event for match %s: %s", request.event.match_id, request.event.description)
        return match_pb2.PushEventResponse(ok=True)


def serve() -> None:
    logging.basicConfig(level=logging.INFO)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    repo = MatchRepository()

    # Add a demo match so the system works out of the box.
    demo_match = common_pb2.Match(
        id="1",
        home_team_id="ARG",
        away_team_id="FRA",
        kick_off_utc="2022-12-18T15:00:00Z",
        stage="Final",
    )
    repo.add_match(demo_match)

    match_pb2_grpc.add_MatchServiceServicer_to_server(MatchServiceServicer(repo), server)
    server.add_insecure_port(f"[::]:{MATCH_SERVICE_PORT}")
    logger.info("MatchService listening on port %d", MATCH_SERVICE_PORT)
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()


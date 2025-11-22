import logging
from concurrent import futures
from typing import Dict, List

import grpc

from config import TEAM_SERVICE_PORT

from generated import team_pb2, team_pb2_grpc, common_pb2


logger = logging.getLogger(__name__)


class TeamRepository:
    """In-memory repository storing team information."""

    def __init__(self) -> None:
        self._teams: Dict[str, common_pb2.Team] = {}

    def add_team(self, team: common_pb2.Team) -> None:
        self._teams[team.id] = team

    def get_team(self, team_id: str) -> common_pb2.Team | None:
        return self._teams.get(team_id)

    def list_teams(self) -> List[common_pb2.Team]:
        return list(self._teams.values())


class TeamServiceServicer(team_pb2_grpc.TeamServiceServicer):
    def __init__(self, repo: TeamRepository) -> None:
        self._repo = repo

    def GetTeam(self, request: team_pb2.GetTeamRequest, context) -> team_pb2.GetTeamResponse:
        team = self._repo.get_team(request.team_id)
        if not team:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Team not found")
            return team_pb2.GetTeamResponse()
        return team_pb2.GetTeamResponse(team=team)

    def ListTeams(self, request: team_pb2.ListTeamsRequest, context) -> team_pb2.ListTeamsResponse:
        teams = self._repo.list_teams()
        return team_pb2.ListTeamsResponse(teams=teams)


def serve() -> None:
    logging.basicConfig(level=logging.INFO)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    repo = TeamRepository()

    # Demo teams for out-of-the-box usage.
    repo.add_team(
        common_pb2.Team(
            id="ARG",
            name="Argentina",
            country="Argentina",
            elo_rating=2100,
        )
    )
    repo.add_team(
        common_pb2.Team(
            id="FRA",
            name="France",
            country="France",
            elo_rating=2050,
        )
    )

    team_pb2_grpc.add_TeamServiceServicer_to_server(TeamServiceServicer(repo), server)
    server.add_insecure_port(f"[::]:{TEAM_SERVICE_PORT}")
    logger.info("TeamService listening on port %d", TEAM_SERVICE_PORT)
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()


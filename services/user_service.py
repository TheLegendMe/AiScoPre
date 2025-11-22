import logging
import secrets
from concurrent import futures
from typing import Dict

import grpc

from config import USER_SERVICE_PORT

from generated import user_pb2, user_pb2_grpc


logger = logging.getLogger(__name__)


class UserRepository:
    """Very simple in-memory user store."""

    def __init__(self) -> None:
        self._users_by_name: Dict[str, str] = {}
        self._passwords: Dict[str, str] = {}

    def register(self, username: str, password: str) -> str:
        if username in self._users_by_name:
            raise ValueError("username already exists")
        user_id = f"user-{len(self._users_by_name) + 1}"
        self._users_by_name[username] = user_id
        # WARNING: demo only, password stored in clear text.
        self._passwords[user_id] = password
        return user_id

    def authenticate(self, username: str, password: str) -> str | None:
        user_id = self._users_by_name.get(username)
        if not user_id:
            return None
        if self._passwords.get(user_id) != password:
            return None
        return user_id


class UserServiceServicer(user_pb2_grpc.UserServiceServicer):
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    def Register(self, request: user_pb2.RegisterRequest, context) -> user_pb2.RegisterResponse:
        try:
            user_id = self._repo.register(request.username, request.password)
        except ValueError as exc:
            context.set_code(grpc.StatusCode.ALREADY_EXISTS)
            context.set_details(str(exc))
            return user_pb2.RegisterResponse()
        return user_pb2.RegisterResponse(user_id=user_id)

    def Login(self, request: user_pb2.LoginRequest, context) -> user_pb2.LoginResponse:
        user_id = self._repo.authenticate(request.username, request.password)
        if not user_id:
            context.set_code(grpc.StatusCode.PERMISSION_DENIED)
            context.set_details("invalid credentials")
            return user_pb2.LoginResponse()
        token = secrets.token_hex(16)
        # For demo purposes, token is not persisted or validated.
        return user_pb2.LoginResponse(user_id=user_id, token=token)


def serve() -> None:
    logging.basicConfig(level=logging.INFO)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    repo = UserRepository()
    user_pb2_grpc.add_UserServiceServicer_to_server(UserServiceServicer(repo), server)
    server.add_insecure_port(f"[::]:{USER_SERVICE_PORT}")
    logger.info("UserService listening on port %d", USER_SERVICE_PORT)
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()


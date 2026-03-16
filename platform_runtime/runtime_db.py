from __future__ import annotations

import json
import os
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

import pymysql


def _project_name() -> str:
    return (
        os.environ.get("PROJECT_NAME")
        or os.environ.get("COMPOSE_PROJECT_NAME")
        or "liderahenk-test"
    )


@dataclass(frozen=True)
class RuntimeDbConfig:
    hosts: tuple[tuple[str, int], ...]
    user: str
    password: str
    database: str


class RuntimeDbAdapter:
    def __init__(self, config: RuntimeDbConfig):
        self.config = config

    @classmethod
    def from_env(cls) -> "RuntimeDbAdapter":
        hosts: list[tuple[str, int]] = []
        env_host = os.environ.get("MYSQL_HOST", "127.0.0.1")
        env_port = int(os.environ.get("MYSQL_PORT", "3306"))
        hosts.append((env_host, env_port))
        for candidate in cls._docker_hosts():
            if candidate not in hosts:
                hosts.append(candidate)
        config = RuntimeDbConfig(
            hosts=tuple(hosts),
            user=os.environ.get("MYSQL_USER", "lider"),
            password=os.environ.get("MYSQL_PASSWORD", "DEGISTIR"),
            database=os.environ.get("MYSQL_DATABASE", "liderahenk"),
        )
        return cls(config)

    @staticmethod
    def _docker_hosts() -> list[tuple[str, int]]:
        project = _project_name()
        filters = [
            "docker",
            "ps",
            "--filter",
            f"label=com.docker.compose.project={project}",
            "--filter",
            "label=com.docker.compose.service=mariadb",
            "--format",
            "{{.ID}}",
        ]
        try:
            output = subprocess.check_output(filters, text=True).strip().splitlines()
        except Exception:
            return []

        hosts: list[tuple[str, int]] = []
        for container_id in output:
            if not container_id:
                continue
            try:
                inspect = subprocess.check_output(
                    [
                        "docker",
                        "inspect",
                        "-f",
                        "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}",
                        container_id,
                    ],
                    text=True,
                ).strip()
            except Exception:
                continue
            for address in inspect.split():
                if address:
                    hosts.append((address, 3306))
        return hosts

    @contextmanager
    def connect(self) -> Iterator[pymysql.connections.Connection]:
        last_error: Exception | None = None
        for host, port in self.config.hosts:
            try:
                connection = pymysql.connect(
                    host=host,
                    port=port,
                    user=self.config.user,
                    password=self.config.password,
                    database=self.config.database,
                    connect_timeout=5,
                    cursorclass=pymysql.cursors.DictCursor,
                )
                try:
                    yield connection
                    return
                finally:
                    connection.close()
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"Unable to connect to MariaDB runtime state: {last_error}")

    def connection_healthy(self) -> bool:
        try:
            with self.connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            return True
        except Exception:
            return False

    def list_c_agents(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM c_agent")
                return list(cursor.fetchall())

    def get_c_agent_count(self) -> int:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS total FROM c_agent")
                row = cursor.fetchone() or {}
                return int(row.get("total", 0))

    def get_config_value(self, name: str = "liderConfigParams") -> str | None:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT value FROM c_config WHERE name = %s", (name,))
                row = cursor.fetchone()
                if not row:
                    return None
                return row.get("value")

    def get_config_json(self, name: str = "liderConfigParams") -> dict[str, Any]:
        value = self.get_config_value(name=name)
        if not value:
            return {}
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8")
        if isinstance(value, dict):
            return value
        return json.loads(value)

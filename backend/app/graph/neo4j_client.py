from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator, Iterable

from neo4j import GraphDatabase, Driver, Session

from app.config import get_settings


class Neo4jClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._driver: Driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        self.database = settings.neo4j_database

    def close(self) -> None:
        self._driver.close()

    def verify(self) -> None:
        self._driver.verify_connectivity()

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        session = self._driver.session(database=self.database)
        try:
            yield session
        finally:
            session.close()

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with self.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def run_write(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with self.session() as session:
            result = session.execute_write(
                lambda tx: [r.data() for r in tx.run(query, parameters or {})]
            )
            return result

    def run_many(self, statements: Iterable[tuple[str, dict[str, Any]]]) -> None:
        with self.session() as session:
            def work(tx):
                for query, params in statements:
                    tx.run(query, params)

            session.execute_write(work)


_client: Neo4jClient | None = None


def get_neo4j() -> Neo4jClient:
    global _client
    if _client is None:
        _client = Neo4jClient()
    return _client

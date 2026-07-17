from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator, Iterable

from neo4j import GraphDatabase, Driver, Session

from app.config import get_settings


class Neo4jClient:
    def __init__(self) -> None:
        settings = get_settings()
        uri = (settings.neo4j_uri or "").strip()
        # Aura requires neo4j+s:// (encrypted). Common misconfig: bolt:// or neo4j://
        self._driver: Driver = GraphDatabase.driver(
            uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        # Empty / whitespace → use Aura/server home database (avoids DatabaseNotFound on some Aura Free instances)
        db = (settings.neo4j_database or "").strip()
        self.database: str | None = db or None

    def close(self) -> None:
        self._driver.close()

    def verify(self) -> None:
        self._driver.verify_connectivity()
        # Force a real query so wrong database names fail at startup
        with self.session() as session:
            session.run("RETURN 1 AS ok").consume()

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        kwargs: dict[str, Any] = {}
        if self.database:
            kwargs["database"] = self.database
        session = self._driver.session(**kwargs)
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


def reset_neo4j_client() -> None:
    """Drop cached client (useful after env changes in tests)."""
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
        _client = None

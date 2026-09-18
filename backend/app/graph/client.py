"""Small async Neo4j wrapper; tests use InMemoryCausalGraph instead."""

from typing import Any

from app.config import settings


class Neo4jGraphClient:
    """Owns an optional async Neo4j driver and its connection lifecycle."""

    def __init__(
        self, uri: str | None = None, user: str | None = None, password: str | None = None
    ) -> None:
        self.uri = uri or settings.NEO4J_URI
        self.user = user or settings.NEO4J_USER
        self.password = password or settings.NEO4J_PASSWORD
        self._driver: Any | None = None

    async def connect(self) -> None:
        if self._driver is None:
            from neo4j import AsyncGraphDatabase

            self._driver = AsyncGraphDatabase.driver(self.uri, auth=(self.user, self.password))

    async def close(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    async def healthcheck(self) -> bool:
        try:
            await self.connect()
            assert self._driver is not None
            await self._driver.verify_connectivity()
            return True
        except Exception:
            return False

    async def run(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        await self.connect()
        assert self._driver is not None
        async with self._driver.session() as session:
            result = await session.run(query, parameters or {})
            return [record.data() async for record in result]

from neo4j import GraphDatabase, Driver
from contextlib import contextmanager
from typing import Generator, Any
import logging
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


def _convert_neo4j_types(value: Any) -> Any:
    """Convert Neo4j types to standard Python types for JSON serialization."""
    if value is None:
        return None
    # Handle Neo4j DateTime
    if hasattr(value, 'to_native'):
        return value.to_native()
    if hasattr(value, 'iso_format'):
        return value.iso_format()
    # Handle lists
    if isinstance(value, list):
        return [_convert_neo4j_types(v) for v in value]
    # Handle dicts
    if isinstance(value, dict):
        return {k: _convert_neo4j_types(v) for k, v in value.items()}
    return value


def sanitize_record(record: dict) -> dict:
    """Sanitize a Neo4j record, converting all special types to Python types."""
    return _convert_neo4j_types(record)


class Neo4jConnection:
    _driver: Driver | None = None

    @classmethod
    def get_driver(cls) -> Driver:
        if cls._driver is None:
            cls._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
        return cls._driver

    @classmethod
    def close(cls) -> None:
        if cls._driver is not None:
            cls._driver.close()
            cls._driver = None

    @classmethod
    @contextmanager
    def get_session(cls) -> Generator:
        driver = cls.get_driver()
        session = driver.session()
        try:
            yield session
        finally:
            session.close()


def init_database() -> None:
    """Initialize database with constraints and indexes for optimal performance."""
    with Neo4jConnection.get_session() as session:
        # Create constraints for unique identifiers
        constraints = [
            "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT post_id IF NOT EXISTS FOR (p:Post) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT location_name IF NOT EXISTS FOR (l:Location) REQUIRE l.name IS UNIQUE",
            "CREATE CONSTRAINT account_username IF NOT EXISTS FOR (a:Account) REQUIRE a.username IS UNIQUE",
            "CREATE CONSTRAINT hashtag_name IF NOT EXISTS FOR (h:Hashtag) REQUIRE h.name IS UNIQUE",
        ]

        # Create indexes for frequently queried properties
        indexes = [
            "CREATE INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.name)",
            "CREATE INDEX post_date IF NOT EXISTS FOR (p:Post) ON (p.posted_at)",
            "CREATE INDEX post_shortcode IF NOT EXISTS FOR (p:Post) ON (p.shortcode)",
            "CREATE INDEX location_coords IF NOT EXISTS FOR (l:Location) ON (l.latitude, l.longitude)",
            "CREATE FULLTEXT INDEX caption_search IF NOT EXISTS FOR (p:Post) ON EACH [p.caption]",
        ]

        for constraint in constraints:
            try:
                session.run(constraint)
                logger.info(f"Created constraint: {constraint}")
            except Exception as e:
                logger.debug(f"Constraint may already exist: {e}")

        for index in indexes:
            try:
                session.run(index)
                logger.info(f"Created index: {index}")
            except Exception as e:
                logger.debug(f"Index may already exist: {e}")

        logger.info("Database initialization complete")


def execute_query(query: str, parameters: dict[str, Any] | None = None) -> list[dict]:
    """Execute a Cypher query and return results with sanitized types."""
    with Neo4jConnection.get_session() as session:
        result = session.run(query, parameters or {})
        return [sanitize_record(record.data()) for record in result]


def execute_write(query: str, parameters: dict[str, Any] | None = None) -> Any:
    """Execute a write query within a transaction with sanitized results."""
    with Neo4jConnection.get_session() as session:
        result = session.execute_write(lambda tx: tx.run(query, parameters or {}).data())
        return [sanitize_record(r) for r in result] if result else result

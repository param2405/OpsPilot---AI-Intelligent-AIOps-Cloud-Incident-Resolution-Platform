from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Generator[None, None, None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def ready_db() -> MagicMock:
    session = MagicMock(spec=Session)
    session.execute.return_value = None
    return session


@pytest.fixture
def unavailable_db() -> MagicMock:
    from sqlalchemy.exc import OperationalError

    session = MagicMock(spec=Session)
    session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("refused"))
    return session


def override_db(mock_session: Any) -> None:
    def _get_db() -> Generator[Any, None, None]:
        yield mock_session

    app.dependency_overrides[get_db] = _get_db

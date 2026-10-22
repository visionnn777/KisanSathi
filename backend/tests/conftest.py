"""Shared test setup. Tests use a throw-away SQLite file, so they never touch your real data.

Owner: Member A
Run from the backend folder:  python -m pytest
"""
import os
import tempfile
from pathlib import Path

# These must be set BEFORE the app is imported.
_tmp = Path(tempfile.mkdtemp(prefix="kisansaathi-test-"))
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_tmp / 'test.db'}")
os.environ["PRELOAD_MODEL"] = "0"
os.environ["MANDI_AUTO_REFRESH_ENABLED"] = "0"
os.environ["MANDI_REFRESH_ON_STARTUP"] = "0"
os.environ["MODEL_DIR"] = str(_tmp / "no-model")
os.environ["DATA_GOV_API_KEY"] = "test-key"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    from app.services import rate_limit
    rate_limit.reset()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session

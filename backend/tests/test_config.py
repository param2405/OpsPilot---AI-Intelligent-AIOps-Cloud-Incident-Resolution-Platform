from app.core.config import Settings


def test_cors_origins_are_parsed() -> None:
    settings = Settings(backend_cors_origins="http://localhost:5173, http://example.test")
    assert settings.cors_origin_list == ["http://localhost:5173", "http://example.test"]


def test_database_url_override_wins() -> None:
    settings = Settings(database_url="postgresql+psycopg://user:pass@db:5432/app")
    assert settings.sqlalchemy_database_uri == "postgresql+psycopg://user:pass@db:5432/app"


def test_password_is_urlencoded_in_built_uri() -> None:
    settings = Settings(postgres_password="p@ss/word")
    assert "p%40ss%2Fword" in settings.sqlalchemy_database_uri

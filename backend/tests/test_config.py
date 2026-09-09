from api.config import settings


def test_cors_origins_parsed_from_csv():
    assert settings.CORS_ORIGINS == ["http://a", "http://b"]


def test_redis_url_format():
    assert settings.REDIS_URL.startswith("redis://")
    assert ":6379/" in settings.REDIS_URL


def test_jwt_secret_min_length():
    assert len(settings.JWT_SECRET_KEY) >= 32

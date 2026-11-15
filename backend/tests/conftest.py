"""Shared pytest fixtures — set env vars before backend modules import."""

import os

os.environ.setdefault("DB_PASSWORD", "test_pw")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "3306")
os.environ.setdefault("JWT_SECRET_KEY", "x" * 48)
os.environ.setdefault("MQTT_BROKER", "localhost")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("CORS_ORIGINS", "http://a,http://b")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "test-admin-pw")

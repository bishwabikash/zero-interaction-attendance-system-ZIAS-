import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import hash_password
from api.database import get_db
from api.db_models import Base, User, UserRoleEnum
from main import app

PASSWORD = "correct horse battery"


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    with Session() as db:
        db.add(User(username="admin", password_hash=hash_password(PASSWORD), role=UserRoleEnum.ADMIN))
        db.commit()

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def auth(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_login_rejects_wrong_password(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "nope"})
    assert response.status_code == 401


def test_login_then_me(client, auth):
    me = client.get("/api/v1/auth/me", headers=auth)
    assert me.status_code == 200
    assert me.json()["username"] == "admin"
    assert me.json()["role"] == "admin"


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer not-a-token"}], ids=["no-token", "bad-token"])
def test_protected_routes_answer_401(client, headers):
    # The frontend logs the user out on 401, so a missing token must not be a 403.
    assert client.get("/api/v1/students/", headers=headers).status_code == 401


def test_students_create_list_and_duplicate(client, auth):
    student = {"student_id": "S1", "stud_name": "Asha Rao", "RFID": "04 AB CD EF"}
    assert client.post("/api/v1/students/", json=student, headers=auth).status_code == 201
    assert client.post("/api/v1/students/", json=student, headers=auth).status_code == 400

    listing = client.get("/api/v1/students/", headers=auth).json()
    assert [s["student_id"] for s in listing] == ["S1"]
    assert client.get("/api/v1/students/NOPE", headers=auth).status_code == 404


def test_device_register_heartbeat_and_list(client, auth):
    device = {"device_id": "room101_door_in", "cluster_id": 101, "room_value": "Room 101", "direction": "entry"}
    assert client.post("/api/v1/devices/register", json=device, headers=auth).status_code == 201

    heartbeat = {"has_rfid": True, "has_pir": True, "ip_address": "10.0.0.5", "firmware_version": "2.1"}
    assert client.post("/api/v1/devices/room101_door_in/heartbeat", json=heartbeat).status_code == 200
    assert client.post("/api/v1/devices/unknown/heartbeat", json=heartbeat).status_code == 404

    listed = client.get("/api/v1/devices/", headers=auth).json()["devices"]
    assert listed[0]["device_id"] == "room101_door_in"
    assert listed[0]["direction"] == "entry"
    assert listed[0]["has_rfid"] is True


def test_attendance_event_shows_up_everywhere(client, auth):
    student = {"student_id": "S1", "stud_name": "Asha Rao", "RFID": "04 AB CD EF"}
    client.post("/api/v1/students/", json=student, headers=auth)
    event = {"student_id": "S1", "event_type": "entry", "source": "rfid", "location": "Room 101"}
    assert client.post("/api/v1/attendance/event", json=event, headers=auth).status_code == 201

    records = client.get("/api/v1/attendance/records", headers=auth).json()
    assert records["total"] == 1
    assert records["records"][0]["status"] == "entry"
    assert records["records"][0]["student_name"] == "Asha Rao"

    stats = client.get("/api/v1/attendance/stats", headers=auth).json()
    assert stats["total_students"] == 1
    assert stats["present_today"] == 1

    occupancy = client.get("/api/v1/attendance/realtime/Room 101", headers=auth).json()
    assert occupancy["current_occupancy"] == 1
    assert occupancy["students"][0]["student_id"] == "S1"


def test_openapi_schema_builds(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/auth/login" in response.json()["paths"]


def test_websocket_says_hello(client):
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "hello"

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from api.db_models import (
    Base,
    DeviceStatusEnum,
    DeviceTypeEnum,
    DirectionEnum,
    User,
    UserDevice,
    UserRoleEnum,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        yield db


def _raw(db, sql):
    return db.execute(text(sql)).scalar()


def test_enums_are_stored_as_lowercase_values(session):
    session.add(User(username="a", password_hash="x", role=UserRoleEnum.ADMIN))
    session.add(
        UserDevice(
            device_id="d1",
            cluster_ID=1,
            room_value="Room 1",
            device_type=DeviceTypeEnum.BLE_BEACON,
            direction=DirectionEnum.EXIT,
            status=DeviceStatusEnum.MAINTENANCE,
        )
    )
    session.commit()

    assert _raw(session, "select role from users") == "admin"
    assert _raw(session, "select device_type from user_devices") == "ble_beacon"
    assert _raw(session, "select direction from user_devices") == "exit"
    assert _raw(session, "select status from user_devices") == "maintenance"


def test_rows_written_by_the_sql_schema_can_be_read(session):
    # docs/database_schema.sql defines these columns with lowercase ENUM values,
    # and MySQL returns them in that case.
    session.execute(
        text(
            "insert into users (username, password_hash, role, is_active, created_at) "
            "values ('b', 'x', 'teacher', 1, '2026-01-01')"
        )
    )
    session.execute(
        text(
            "insert into user_devices (device_id, cluster_ID, device_type, direction, room_value, status, created_at) "
            "values ('d2', 1, 'rfid', 'both', 'Room 2', 'inactive', '2026-01-01')"
        )
    )
    session.commit()

    assert session.query(User).filter_by(username="b").one().role is UserRoleEnum.TEACHER
    device = session.query(UserDevice).filter_by(device_id="d2").one()
    assert device.device_type is DeviceTypeEnum.RFID
    assert device.direction is DirectionEnum.BOTH
    assert device.status is DeviceStatusEnum.INACTIVE

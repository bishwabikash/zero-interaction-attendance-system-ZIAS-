-- ZIAS database schema — MySQL 8.x / MariaDB 10.5+.
-- init_db() in the FastAPI service will create these tables idempotently,
-- but this file is authoritative and also runs on first MySQL container boot.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(120) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'teacher', 'viewer') NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS student (
    student_id VARCHAR(20) PRIMARY KEY,
    stud_name VARCHAR(100) NOT NULL,
    RFID VARCHAR(50) UNIQUE,
    email VARCHAR(100),
    phone VARCHAR(15),
    class_section VARCHAR(30),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_student_rfid (RFID),
    INDEX idx_student_class (class_section)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS user_devices (
    device_id VARCHAR(50) PRIMARY KEY,
    cluster_ID INT NOT NULL,
    device_type ENUM('rfid', 'pir', 'ble_beacon', 'universal') NOT NULL DEFAULT 'universal',
    direction ENUM('entry', 'exit', 'both') NOT NULL DEFAULT 'entry',
    room_value VARCHAR(50) NOT NULL,
    location_description VARCHAR(200),
    has_rfid BOOLEAN DEFAULT FALSE,
    has_pir BOOLEAN DEFAULT FALSE,
    has_ble BOOLEAN DEFAULT FALSE,
    has_camera BOOLEAN DEFAULT FALSE,
    firmware_version VARCHAR(20),
    ip_address VARCHAR(45),
    last_seen TIMESTAMP NULL,
    status ENUM('active', 'inactive', 'maintenance') DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_devices_cluster (cluster_ID),
    INDEX idx_devices_room (room_value)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sensor_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_ID VARCHAR(50) NOT NULL,
    cluster_ID INT NOT NULL,
    RFID VARCHAR(50),
    time_stamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sensor_active BOOLEAN DEFAULT TRUE,
    processed BOOLEAN DEFAULT FALSE,
    INDEX idx_sensor_time (time_stamp),
    INDEX idx_sensor_cluster (cluster_ID),
    INDEX idx_sensor_device (device_ID),
    INDEX idx_sensor_rfid (RFID),
    INDEX idx_sensor_processed (processed),
    CONSTRAINT fk_sensor_device
        FOREIGN KEY (device_ID) REFERENCES user_devices(device_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS entry_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(20),
    student_name VARCHAR(100),
    RFID VARCHAR(50),
    room_value VARCHAR(50),
    status INT NOT NULL COMMENT '1=entry, -1=exit',
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confidence FLOAT DEFAULT 1.0,
    source VARCHAR(20) DEFAULT 'rfid',
    INDEX idx_log_student (student_id),
    INDEX idx_log_rfid (RFID),
    INDEX idx_log_timestamp (timestamp),
    INDEX idx_log_room (room_value),
    CONSTRAINT fk_log_student
        FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS attendance_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    total_hours DECIMAL(5,2) DEFAULT 0,
    first_entry TIMESTAMP NULL,
    last_exit TIMESTAMP NULL,
    entry_count INT DEFAULT 0,
    UNIQUE KEY uq_student_date (student_id, date),
    INDEX idx_summary_date (date),
    CONSTRAINT fk_summary_student
        FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ble_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(20) NOT NULL,
    beacon_uuid VARCHAR(100) NOT NULL,
    rssi INT,
    latitude DOUBLE,
    longitude DOUBLE,
    event_type VARCHAR(20),
    app_version VARCHAR(20),
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE,
    INDEX idx_ble_student (student_id),
    INDEX idx_ble_beacon (beacon_uuid),
    INDEX idx_ble_time (timestamp),
    CONSTRAINT fk_ble_student
        FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Handy views.
CREATE OR REPLACE VIEW v_current_occupancy AS
SELECT room_value,
       COUNT(DISTINCT student_id) AS occupants
FROM entry_log e
WHERE (student_id, timestamp) IN (
    SELECT student_id, MAX(timestamp) FROM entry_log
    WHERE timestamp >= (NOW() - INTERVAL 12 HOUR)
    GROUP BY student_id
)
AND status = 1
GROUP BY room_value;

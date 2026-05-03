-- =========================================
-- AI EXAM MONITORING SYSTEM 
-- =========================================

CREATE DATABASE IF NOT EXISTS ai_exam_monitoring;
USE ai_exam_monitoring;

-- =========================================
-- USERS
-- =========================================
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================
-- PASSWORD RESET 
-- =========================================
CREATE TABLE password_resets (
    id INT AUTO_INCREMENT PRIMARY KEY,

    user_id INT NOT NULL,
    token VARCHAR(255) NOT NULL UNIQUE,
    expires_at DATETIME NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE,

    INDEX idx_token (token)
);

-- =========================================
-- CAMERAS
-- =========================================
CREATE TABLE cameras (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    source VARCHAR(255) NOT NULL,
    location VARCHAR(100),
    status ENUM('active','inactive') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================
-- SESSIONS
-- =========================================
CREATE TABLE sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,

    name VARCHAR(100) NOT NULL,
    description TEXT,

    session_date DATE NOT NULL,

    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,

    status ENUM('scheduled','active','completed') DEFAULT 'scheduled',

    -- REPORT SYSTEM
    report_generated BOOLEAN DEFAULT FALSE,
    report_path VARCHAR(255),
    report_generated_at DATETIME,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Prevent duplicate sessions
    UNIQUE KEY unique_session (session_date, start_time, end_time)
);

-- =========================================
-- EVENTS (AI LOGS)
-- =========================================
CREATE TABLE events (
    id INT AUTO_INCREMENT PRIMARY KEY,

    camera_id INT,

    status ENUM('SUSPICIOUS','CHEATING') NOT NULL,
    reason TEXT,
    score INT,

    snapshot VARCHAR(255),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (camera_id) REFERENCES cameras(id)
    ON DELETE SET NULL
);


-- =========================================
CREATE TABLE session_reports (
    id INT AUTO_INCREMENT PRIMARY KEY,

    session_id INT NOT NULL,
    report_data JSON,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (session_id) REFERENCES sessions(id)
    ON DELETE CASCADE
);

-- =========================================
-- PERFORMANCE INDEXES
-- =========================================

-- EVENTS
CREATE INDEX idx_events_time ON events(created_at);
CREATE INDEX idx_events_status ON events(status);
CREATE INDEX idx_events_camera ON events(camera_id);

-- SESSIONS
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_date ON sessions(session_date);
CREATE INDEX idx_sessions_name ON sessions(name);
CREATE INDEX idx_sessions_report ON sessions(report_generated);

-- SEARCH OPTIMIZATION
CREATE INDEX idx_sessions_search ON sessions(session_date, name, status);

-- USERS
CREATE INDEX idx_users_email ON users(email);

-- =========================================
-- DEFAULT CAMERA
-- =========================================
INSERT INTO cameras (name, source, location)
VALUES ('Laptop Camera', '0', 'Local Device');

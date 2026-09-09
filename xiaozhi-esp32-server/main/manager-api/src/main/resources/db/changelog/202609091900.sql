CREATE TABLE model_service_reminder (service_key VARCHAR(64) PRIMARY KEY, renewal_date DATE NULL, updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP);

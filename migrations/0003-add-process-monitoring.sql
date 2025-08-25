-- Migration to add process monitoring tables
-- Created: 2025-08-25

-- Table to track background processes and their status
CREATE TABLE IF NOT EXISTS process_status (
    process_name TEXT PRIMARY KEY,
    process_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'stopped',
    pid INTEGER,
    started_at DATETIME,
    last_heartbeat DATETIME,
    last_activity DATETIME,
    restart_count INTEGER DEFAULT 0,
    error_message TEXT,
    config_data TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Table to log process events and activities
CREATE TABLE IF NOT EXISTS process_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    process_name TEXT NOT NULL,
    log_level TEXT NOT NULL, -- 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    event_type TEXT NOT NULL, -- 'start', 'stop', 'heartbeat', 'activity', 'error', 'restart'
    message TEXT NOT NULL,
    details TEXT, -- JSON string for additional context
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (process_name) REFERENCES process_status(process_name)
);

-- Table to track specific activity metrics for each process
CREATE TABLE IF NOT EXISTS process_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    process_name TEXT NOT NULL,
    metric_name TEXT NOT NULL, -- 'messages_processed', 'posts_sent', 'errors_count', etc.
    metric_value INTEGER NOT NULL,
    metric_type TEXT DEFAULT 'counter', -- 'counter', 'gauge', 'histogram'
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (process_name) REFERENCES process_status(process_name)
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_process_logs_process_timestamp ON process_logs(process_name, timestamp);
CREATE INDEX IF NOT EXISTS idx_process_logs_level ON process_logs(log_level);
CREATE INDEX IF NOT EXISTS idx_process_metrics_process_metric ON process_metrics(process_name, metric_name);
CREATE INDEX IF NOT EXISTS idx_process_metrics_timestamp ON process_metrics(recorded_at);

-- Insert initial process definitions
INSERT OR IGNORE INTO process_status (process_name, process_type, status) VALUES 
    ('firehose_ingester', 'firehose', 'stopped'),
    ('bluesky_automation', 'bluesky_automation', 'stopped');

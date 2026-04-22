-- WhiteFlows Elite: Cloudflare D1 Initialisation Schema
-- Run this via: npx wrangler d1 execute whiteflows_prod --file=schema.sql

-- Leads Table
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    mobile TEXT,
    json_data TEXT,
    created_at TIMESTAMP DEFAULT (datetime('now'))
);

-- Applications Table
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id TEXT UNIQUE,
    applicant_name TEXT,
    email TEXT,
    mobile TEXT,
    json_data TEXT,
    created_at TIMESTAMP DEFAULT (datetime('now'))
);

-- Metadata Table
CREATE TABLE IF NOT EXISTS server_metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);

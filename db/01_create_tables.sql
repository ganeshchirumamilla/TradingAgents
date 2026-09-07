-- Market Data Historical Tables
-- PostgreSQL schema for TradingAgents system
-- Created: 2026-09-06

-- Daily historical data
CREATE TABLE IF NOT EXISTS historical_data_daily (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    date TIMESTAMP NOT NULL,
    open DECIMAL(10,2),
    high DECIMAL(10,2),
    low DECIMAL(10,2),
    close DECIMAL(10,2),
    volume BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

-- Hourly historical data
CREATE TABLE IF NOT EXISTS historical_data_hourly (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    date TIMESTAMP NOT NULL,
    open DECIMAL(10,2),
    high DECIMAL(10,2),
    low DECIMAL(10,2),
    close DECIMAL(10,2),
    volume BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

-- 5-minute historical data
CREATE TABLE IF NOT EXISTS historical_data_5min (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    date TIMESTAMP NOT NULL,
    open DECIMAL(10,2),
    high DECIMAL(10,2),
    low DECIMAL(10,2),
    close DECIMAL(10,2),
    volume BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

-- 1-minute historical data
CREATE TABLE IF NOT EXISTS historical_data_1min (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    date TIMESTAMP NOT NULL,
    open DECIMAL(10,2),
    high DECIMAL(10,2),
    low DECIMAL(10,2),
    close DECIMAL(10,2),
    volume BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_daily_ticker_date ON historical_data_daily(ticker, date DESC);
CREATE INDEX IF NOT EXISTS idx_hourly_ticker_date ON historical_data_hourly(ticker, date DESC);
CREATE INDEX IF NOT EXISTS idx_5min_ticker_date ON historical_data_5min(ticker, date DESC);
CREATE INDEX IF NOT EXISTS idx_1min_ticker_date ON historical_data_1min(ticker, date DESC);

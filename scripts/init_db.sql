-- TradingAgents Database Initialization Script
-- PostgreSQL 16+

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Table: Backtest Runs
CREATE TABLE IF NOT EXISTS backtest_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker VARCHAR(20) NOT NULL,
    strategy_name VARCHAR(100) NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    initial_capital DECIMAL(15,2) NOT NULL,
    final_capital DECIMAL(15,2) NOT NULL,
    total_return DECIMAL(10,4) NOT NULL,
    sharpe_ratio DECIMAL(10,4),
    sortino_ratio DECIMAL(10,4),
    calmar_ratio DECIMAL(10,4),
    max_drawdown DECIMAL(10,4),
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(10,4),
    avg_win DECIMAL(15,2),
    avg_loss DECIMAL(15,2),
    profit_factor DECIMAL(10,4),
    parameters JSONB,
    trades JSONB,
    equity_curve JSONB,
    signals JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),
    status VARCHAR(50) DEFAULT 'completed'
);

CREATE INDEX idx_backtest_runs_ticker ON backtest_runs(ticker);
CREATE INDEX idx_backtest_runs_strategy ON backtest_runs(strategy_name);
CREATE INDEX idx_backtest_runs_created_at ON backtest_runs(created_at DESC);
CREATE INDEX idx_backtest_runs_status ON backtest_runs(status);

-- Table: Historical Data Cache
CREATE TABLE IF NOT EXISTS historical_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    open DECIMAL(10,4) NOT NULL,
    high DECIMAL(10,4) NOT NULL,
    low DECIMAL(10,4) NOT NULL,
    close DECIMAL(10,4) NOT NULL,
    volume BIGINT,
    adjusted_close DECIMAL(10,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_source VARCHAR(50),
    UNIQUE(ticker, date)
);

CREATE INDEX idx_historical_data_ticker ON historical_data(ticker);
CREATE INDEX idx_historical_data_date ON historical_data(date DESC);
CREATE INDEX idx_historical_data_ticker_date ON historical_data(ticker, date DESC);

-- Table: Trade Signals
CREATE TABLE IF NOT EXISTS trade_signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker VARCHAR(20) NOT NULL,
    date TIMESTAMP NOT NULL,
    signal_type VARCHAR(20) NOT NULL,
    price DECIMAL(10,4) NOT NULL,
    confidence DECIMAL(10,4),
    indicators JSONB,
    strategy_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trade_signals_ticker ON trade_signals(ticker);
CREATE INDEX idx_trade_signals_date ON trade_signals(date DESC);
CREATE INDEX idx_trade_signals_ticker_date ON trade_signals(ticker, date DESC);
CREATE INDEX idx_trade_signals_type ON trade_signals(signal_type);

-- Table: Portfolio Positions
CREATE TABLE IF NOT EXISTS portfolio_positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker VARCHAR(20) NOT NULL UNIQUE,
    shares INTEGER DEFAULT 0,
    average_cost DECIMAL(10,4),
    current_price DECIMAL(10,4),
    pnl DECIMAL(15,2),
    pnl_pct DECIMAL(10,4),
    last_trade_date TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    strategy_name VARCHAR(100)
);

CREATE INDEX idx_portfolio_positions_ticker ON portfolio_positions(ticker);
CREATE INDEX idx_portfolio_positions_updated_at ON portfolio_positions(updated_at DESC);

-- Table: Account Balance History
CREATE TABLE IF NOT EXISTS account_balance_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total_value DECIMAL(15,2) NOT NULL,
    cash DECIMAL(15,2) NOT NULL,
    positions_value DECIMAL(15,2) NOT NULL,
    num_positions INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_account_balance_history_timestamp ON account_balance_history(timestamp DESC);

-- Table: Trades (Individual Executions)
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    backtest_run_id UUID REFERENCES backtest_runs(id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    entry_date TIMESTAMP NOT NULL,
    exit_date TIMESTAMP,
    entry_price DECIMAL(10,4) NOT NULL,
    exit_price DECIMAL(10,4),
    shares INTEGER NOT NULL,
    pnl DECIMAL(15,2),
    pnl_pct DECIMAL(10,4),
    reason VARCHAR(50),
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trades_ticker ON trades(ticker);
CREATE INDEX idx_trades_backtest_run_id ON trades(backtest_run_id);
CREATE INDEX idx_trades_entry_date ON trades(entry_date DESC);
CREATE INDEX idx_trades_status ON trades(status);

-- Table: Strategy Parameters
CREATE TABLE IF NOT EXISTS strategy_parameters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_name VARCHAR(100) NOT NULL,
    parameters JSONB NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),
    UNIQUE(strategy_name, parameters)
);

CREATE INDEX idx_strategy_parameters_name ON strategy_parameters(strategy_name);
CREATE INDEX idx_strategy_parameters_active ON strategy_parameters(is_active);

-- Table: Audit Log
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action VARCHAR(100) NOT NULL,
    table_name VARCHAR(100),
    record_id UUID,
    old_values JSONB,
    new_values JSONB,
    user_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(50)
);

CREATE INDEX idx_audit_log_created_at ON audit_log(created_at DESC);
CREATE INDEX idx_audit_log_table_name ON audit_log(table_name);

-- Table: System Configuration
CREATE TABLE IF NOT EXISTS system_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_key VARCHAR(255) NOT NULL UNIQUE,
    config_value TEXT NOT NULL,
    data_type VARCHAR(50),
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(255)
);

CREATE INDEX idx_system_config_key ON system_config(config_key);

-- Create Views for Analysis

-- View: Backtest Performance Summary
CREATE OR REPLACE VIEW backtest_summary AS
SELECT
    strategy_name,
    COUNT(*) as num_backtests,
    AVG(total_return) as avg_return,
    MAX(total_return) as best_return,
    MIN(total_return) as worst_return,
    AVG(sharpe_ratio) as avg_sharpe,
    AVG(max_drawdown) as avg_max_drawdown,
    AVG(win_rate) as avg_win_rate,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_count
FROM backtest_runs
GROUP BY strategy_name;

-- View: Ticker Performance
CREATE OR REPLACE VIEW ticker_performance AS
SELECT
    ticker,
    COUNT(*) as num_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
    SUM(pnl) as total_pnl,
    AVG(pnl) as avg_pnl,
    MAX(pnl) as best_trade,
    MIN(pnl) as worst_trade
FROM trades
WHERE status = 'closed'
GROUP BY ticker;

-- Create Functions

-- Function: Update timestamp
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply timestamp trigger to tables
CREATE TRIGGER backtest_runs_update_timestamp
BEFORE UPDATE ON backtest_runs
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER strategy_parameters_update_timestamp
BEFORE UPDATE ON strategy_parameters
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();

-- Function: Calculate equity curve from trades
CREATE OR REPLACE FUNCTION calculate_equity_curve(p_backtest_run_id UUID)
RETURNS TABLE(trade_date TIMESTAMP, equity DECIMAL) AS $$
BEGIN
    RETURN QUERY
    WITH ordered_trades AS (
        SELECT
            COALESCE(exit_date, entry_date) as trade_date,
            pnl
        FROM trades
        WHERE backtest_run_id = p_backtest_run_id
        ORDER BY trade_date ASC
    ),
    cumulative_pnl AS (
        SELECT
            trade_date,
            SUM(pnl) OVER (ORDER BY trade_date) as cum_pnl
        FROM ordered_trades
    )
    SELECT
        trade_date,
        (SELECT initial_capital FROM backtest_runs WHERE id = p_backtest_run_id) + cum_pnl as equity
    FROM cumulative_pnl;
END;
$$ LANGUAGE plpgsql;

-- Permissions and Roles
-- Create application user (if not exists)
-- Note: This is run in the docker-compose environment by the postgres service

-- Grant permissions to application user
GRANT SELECT ON backtest_runs TO trading;
GRANT SELECT ON historical_data TO trading;
GRANT SELECT ON trade_signals TO trading;
GRANT SELECT ON portfolio_positions TO trading;
GRANT SELECT ON backtest_summary TO trading;
GRANT SELECT ON ticker_performance TO trading;

-- Insert default system configuration
INSERT INTO system_config (config_key, config_value, data_type, description)
VALUES
    ('max_backtest_days', '365', 'integer', 'Maximum days to backtest'),
    ('min_backtest_capital', '1000', 'decimal', 'Minimum initial capital'),
    ('max_position_size', '0.1', 'decimal', 'Maximum position as % of capital'),
    ('default_commission_rate', '0.001', 'decimal', 'Default commission rate'),
    ('default_slippage_bps', '10', 'decimal', 'Default slippage in basis points')
ON CONFLICT (config_key) DO NOTHING;

-- Create indexes for performance
ANALYZE backtest_runs;
ANALYZE historical_data;
ANALYZE trade_signals;
ANALYZE trades;

COMMIT;

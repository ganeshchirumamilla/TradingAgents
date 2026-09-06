"""Interactive Brokers (IBKR) integration: account context, market data, and order execution.

Everything here is opt-in via ``ibkr_enabled`` / ``ibkr_auto_execute`` in config
(see ``tradingagents/default_config.py``) and lazy-imports the optional
``ib_async`` dependency, so importing this package never requires TWS/IB
Gateway or the extra to be installed.
"""

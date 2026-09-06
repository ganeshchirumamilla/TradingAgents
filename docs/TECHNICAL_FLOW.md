# TradingAgents: Technical and Logical Flow Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Data Flow Pipeline](#data-flow-pipeline)
4. [Agent System](#agent-system)
5. [Graph Structure & State Management](#graph-structure--state-management)
6. [LLM Integration](#llm-integration)
7. [Decision Making Process](#decision-making-process)
8. [Persistence & Recovery](#persistence--recovery)
9. [Broker Integration](#broker-integration)
10. [Technical Implementation Details](#technical-implementation-details)

---

## System Overview

**TradingAgents** is a multi-agent LLM-powered financial trading framework that decomposes complex trading decisions into specialized agent roles that mirror real-world trading firms. The system uses LangGraph as the orchestration engine to coordinate asynchronous agent interactions and state transitions.

### Key Components:
- **CLI Interface**: User-facing command-line application for ticker selection and configuration
- **Graph Engine**: LangGraph-based state machine orchestrating agent workflows
- **Agent System**: Specialized LLM agents with specific roles and responsibilities
- **Data Vendors**: External data sources (yfinance, Alpha Vantage, FRED, Reddit, etc.)
- **LLM Clients**: Multi-provider support (OpenAI, Anthropic, Google, DeepSeek, etc.)
- **Broker Integration**: Interactive Brokers (IBKR) for account context and execution
- **Memory System**: Decision log and checkpoint-based state recovery

---

## Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                       CLI Interface (Typer)                  │
│        User Input: Ticker, Date, LLM Provider, Config        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    TradingAgentsGraph                         │
│              (Main Orchestration Engine)                      │
│  - Initializes LLM clients                                   │
│  - Sets up data vendors                                      │
│  - Creates initial state                                     │
│  - Configures graph workflow                                 │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
    ┌────────────┐  ┌──────────┐  ┌───────────┐
    │ Data Flow  │  │ Analyst  │  │  Debate   │
    │  Pipeline  │  │  Agents  │  │  Managers │
    └────────────┘  └──────────┘  └───────────┘
         │               │               │
         └───────────────┼───────────────┘
                         │
                         ▼
    ┌────────────────────────────────────┐
    │  Trader → Risk Manager → Portfolio │
    │  Manager Decision Sequence          │
    └────────────────────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────┐
    │  Broker Execution (if enabled)     │
    │  Memory Persistence                │
    │  Reporting & Output                │
    └────────────────────────────────────┘
```

### Directory Structure

```
tradingagents/
├── agents/                 # Agent implementations
│   ├── analysts/          # Fundamental, market, sentiment, news analysts
│   ├── researchers/       # Bull and bear researchers
│   ├── risk_mgmt/         # Risk debaters
│   ├── managers/          # Research manager, portfolio manager
│   ├── trader/            # Trader agent
│   ├── utils/             # Tools and utilities for agents
│   └── schemas.py         # Pydantic schemas for structured output
├── dataflows/             # Data acquisition and processing
│   ├── alpha_vantage*.py  # Alpha Vantage integrations
│   ├── y_finance.py       # Yahoo Finance
│   ├── fred.py            # Federal Reserve data
│   ├── reddit.py          # Reddit sentiment
│   ├── yfinance_news.py   # News from yfinance
│   ├── polymarket.py      # Polymarket prediction markets
│   ├── stocktwits.py      # StockTwits sentiment
│   ├── ibkr.py            # Interactive Brokers data
│   └── config.py          # Data vendor configuration
├── graph/                 # Graph orchestration
│   ├── trading_graph.py   # Main orchestrator class
│   ├── propagation.py     # State initialization and propagation
│   ├── conditional_logic.py # Router logic for state transitions
│   ├── setup.py           # Graph construction
│   ├── checkpointer.py    # State persistence
│   ├── reflection.py      # Decision log reflection
│   └── signal_processing.py # Technical analysis signals
├── llm_clients/           # LLM provider clients
│   ├── base_client.py     # Abstract base class
│   ├── anthropic_client.py
│   ├── openai_client.py
│   ├── google_client.py
│   ├── bedrock_client.py
│   ├── factory.py         # Client creation factory
│   ├── capabilities.py    # Model capability registry
│   └── model_catalog.py   # Available models per provider
├── brokers/               # Broker integrations
│   ├── ibkr_client.py     # Interactive Brokers client
│   ├── context.py         # Account context builder
│   └── execution.py       # Order execution logic
├── default_config.py      # Default configuration
├── reporting.py           # Report generation
└── __init__.py

cli/
├── main.py               # CLI entry point
├── utils.py              # CLI utilities
├── stats_handler.py      # LLM stats tracking
└── announcements.py      # News/updates display
```

---

## Data Flow Pipeline

### 1. Data Acquisition Phase

The framework acquires data from multiple vendors before any analysis begins. This ensures all agents reason about the same market snapshot.

```
┌─────────────────────────────────────────────────────────┐
│          Ticker Resolution & Validation                 │
│  - Resolve ticker to company identity (yfinance)        │
│  - Validate exchange and market                         │
│  - Detect asset type (stock/crypto/ETF)                 │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│        Core Stock Data (Multiple Sources)               │
│  - yfinance: price, volume, OHLC                        │
│  - Alpha Vantage: daily quotes, intraday                │
│  - IBKR: if enabled, real-time account quotes           │
│  - Date range: trade_date ± window_days                 │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│           Fundamental Data (Alpha Vantage)              │
│  - Income statement, balance sheet, cash flow           │
│  - Key financial metrics and ratios                     │
│  - TTM (trailing twelve months) calculations            │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│         Technical Indicators (StockStats)               │
│  - MACD, RSI, Bollinger Bands, SMA, EMA                 │
│  - Volume indicators, momentum oscillators              │
│  - Signal detection and threshold crossing              │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│          Sentiment & Alternative Data                   │
│  - News: yfinance news API                              │
│  - Social: StockTwits, Reddit, X                        │
│  - Macro: FRED economic indicators                      │
│  - Prediction: Polymarket event contracts               │
│  - Insider: Insider transactions                        │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│     Data Validation & Point-in-Time Correctness         │
│  - No look-ahead bias (Alpha Vantage hardening)         │
│  - FRED vintage pins (timestamp accuracy)               │
│  - Reddit/Twitter Retry-After handling                  │
│  - Rate limit backoff with jitter                       │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
         ┌───────────────────┐
         │  Verified Snapshot │
         │  (Single Dataframe)│
         └───────────────────┘
```

### 2. Data Vendor Configuration

Data vendors are configured in `tradingagents/dataflows/config.py`:

```python
DEFAULT_DATA_CONFIG = {
    "core_stock_apis": ["yfinance", "alpha_vantage"],  # Fallback order
    "fundamental_apis": ["alpha_vantage"],
    "news_apis": ["yfinance", "alpha_vantage"],
    "macro_apis": ["fred"],
    "sentiment_apis": ["reddit", "stocktwits"],
    "prediction_markets": ["polymarket"],
}
```

**Key Data Flows:**

| Data Type | Source | Tool Function | Output |
|-----------|--------|---------------|--------|
| Price/Volume | yfinance, Alpha Vantage, IBKR | `get_stock_data()` | DataFrame with OHLCV |
| Fundamentals | Alpha Vantage | `get_fundamentals()`, `get_balance_sheet()` | Financial metrics |
| Technical Signals | StockStats | `get_indicators()` | MACD, RSI, Bollinger Bands |
| News | yfinance, Alpha Vantage | `get_news()`, `get_global_news()` | News headlines + sentiment |
| Social Sentiment | Reddit, StockTwits | Parsed via dataflows | Community sentiment |
| Macro Data | FRED | `get_macro_indicators()` | Economic indicators |
| Predictions | Polymarket | `get_prediction_markets()` | Event contract probabilities |
| Account Context | IBKR | `build_ibkr_account_context()` | Position/cash snapshot |

### 3. Data Caching & Rate Limiting

All data vendors implement rate-limit awareness:

```python
# Alpha Vantage: 5 calls/min, exponential backoff
# FRED: No official limit, aggressive polling allowed
# Reddit: Respects Retry-After headers, implements jitter
# StockTwits: 200 calls/hour
```

**Cache Strategy:**
- In-memory cache during single run (no redundant API calls)
- No persistent cache (fresh data each run to avoid staleness)
- Retry logic with configurable `llm_max_retries` budget

---

## Agent System

### Agent Hierarchy & Roles

The framework implements a hierarchical agent structure:

```
                    ┌──────────────────────┐
                    │   Portfolio Manager   │
                    │  (Final Decision)     │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼────────────┐
                    │   Risk Management     │
                    │   - Aggressive Debater│
                    │   - Conservative      │
                    │   - Neutral Debater   │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │    Trader Agent       │
                    │  (Directional Call)   │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │ Research Manager      │
                    │ (Investment Plan)     │
                    └───────────┬────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
    ┌────────────┐         ┌────────────┐         ┌────────────┐
    │   Analyst  │         │   Debate   │         │  Previous  │
    │  Execution │         │  Managers  │         │  Memory    │
    │  - Market  │         │ - Bull vs  │         │  (Context) │
    │  - Social  │         │   Bear     │         │            │
    │  - News    │         │ - Invest   │         │            │
    │  - Fundamentals      │   Debate   │         │            │
    └────────────┘         └────────────┘         └────────────┘
```

### Agent Types & Responsibilities

#### 1. **Analyst Agents** (Parallel Execution)

Each analyst runs independently and produces a research report:

- **Market Analyst**
  - Input: Price data, technical indicators, volume
  - Output: Technical analysis report with signal detections
  - Tools: `get_stock_data()`, `get_indicators()`, technical analysis

- **Social Sentiment Analyst**
  - Input: StockTwits, Reddit posts
  - Output: Sentiment summary and positioning analysis
  - Tools: Reddit/StockTwits data aggregation

- **News Analyst**
  - Input: News headlines, global macroeconomic data
  - Output: News impact assessment and macro analysis
  - Tools: `get_news()`, `get_global_news()`, `get_macro_indicators()`

- **Fundamentals Analyst**
  - Input: Financial statements, key metrics
  - Output: Valuation analysis and red flag identification
  - Tools: `get_fundamentals()`, `get_balance_sheet()`, `get_cashflow()`

**Execution Pattern:**
```python
# Parallel analyst execution
analyst_results = await asyncio.gather(
    market_analyst.invoke(state),
    social_analyst.invoke(state),
    news_analyst.invoke(state),
    fundamentals_analyst.invoke(state),
)
```

#### 2. **Debate Managers**

**Investment Debate** (Bull vs Bear):
- Bull Researcher: Bullish case supported by analyst reports
- Bear Researcher: Bearish case, risk identification
- Judge: Synthesizes both sides into consensus investment plan

**Risk Debate** (Aggressive vs Conservative vs Neutral):
- Aggressive Risk Debater: Risk tolerance perspective
- Conservative Risk Debater: Capital preservation focus
- Neutral Risk Debater: Balanced risk assessment
- Judge: Risk-adjusted decision

**Debate Flow:**
```
Round 1: Bull presents case
Round 2: Bear responds to Bull
Round 3: Bull counter-responds
...
Round N: Judge synthesizes → InvestmentPlan

(Risk debate follows same pattern)
```

#### 3. **Decision-Making Agents**

**Research Manager** (Structured Output):
- Input: Analyst reports + investment debate outcome
- Output: ResearchPlan with:
  - `recommendation`: Buy/Overweight/Hold/Underweight/Sell
  - `rationale`: Why this recommendation
  - `strategic_actions`: Concrete trading instructions
  - `confidence_level`: 1-5 rating

**Trader** (Structured Output):
- Input: ResearchPlan
- Output: TraderAction (Buy/Hold/Sell)
- Logic: Translates 5-tier rating to 3-tier action

**Portfolio Manager** (Structured Output & Execution):
- Input: TraderAction + Risk assessment
- Output: Final PortfolioRating (Buy/Overweight/Hold/Underweight/Sell)
- Checks: Account context (if IBKR enabled), position limits
- Action: Executes order or logs decision

### Agent Lifecycle

```python
class Agent:
    def __init__(self, llm_client, tools, system_prompt):
        self.llm = llm_client
        self.tools = tools  # List of available functions
        self.system_prompt = system_prompt
        self.graph = self.create_runnable()
    
    def invoke(self, state):
        # 1. Format messages with state context
        # 2. Call LLM with tools
        # 3. Tool execution loop (if tool_calls returned)
        # 4. Return final response
        return self.graph.invoke(state)
```

---

## Graph Structure & State Management

### State Definition

The entire agent system shares a unified state object (LangGraph paradigm):

```python
# AgentState (from agent_states.py)
{
    "messages": list,                      # Conversation history
    "company_of_interest": str,            # Ticker/symbol
    "asset_type": str,                     # stock/crypto/etf
    "trade_date": str,                     # YYYY-MM-DD
    "instrument_context": str,             # Company name & context
    "account_context": str,                # IBKR position snapshot
    "past_context": str,                   # Memory log excerpt
    
    # Analyst outputs
    "market_report": str,
    "fundamentals_report": str,
    "sentiment_report": str,
    "news_report": str,
    
    # Debate state machines
    "investment_debate_state": {
        "bull_history": str,
        "bear_history": str,
        "history": str,
        "current_response": str,
        "judge_decision": str,
        "count": int,
    },
    "risk_debate_state": {
        "aggressive_history": str,
        "conservative_history": str,
        "neutral_history": str,
        "history": str,
        "current_aggressive_response": str,
        "current_conservative_response": str,
        "current_neutral_response": str,
        "judge_decision": str,
        "count": int,
    },
}
```

### Graph Construction

Built using LangGraph's `StateGraph` API:

```python
# From graph/setup.py
graph = StateGraph(AgentState)

# Add nodes (agents and action nodes)
graph.add_node("market_analyst", market_analyst.invoke)
graph.add_node("social_analyst", social_analyst.invoke)
graph.add_node("debate_router", debate_logic.route_next_speaker)
graph.add_node("execute_decision", execute_decision)

# Add edges (state transitions)
graph.add_edge("start", "market_analyst")
graph.add_edge("market_analyst", "fundamentals_analyst")
graph.add_conditional_edge("debate_router", debate_logic.should_continue_debate)
graph.add_edge("trader", "portfolio_manager")

# Compile to runnable
agent_graph = graph.compile()
```

### State Transitions (Flow Logic)

```
START
  ↓
[Data Acquisition] → Create initial state with verified data
  ↓
[Analyst Execution] → Run analysts in parallel or sequence
  - market_analyst
  - social_analyst
  - news_analyst
  - fundamentals_analyst
  ↓
[Concatenate Reports] → Merge all analyst outputs into state
  ↓
[Investment Debate] → Loop until max rounds or consensus
  - Bull researcher presents
  - Bear researcher responds (conditional: if debate should continue)
  - Bull counter-responds (conditional)
  - Judge synthesizes → ResearchPlan
  ↓
[Research Manager] → Creates structured InvestmentPlan
  ↓
[Trader] → Translates plan to TraderAction (Buy/Hold/Sell)
  ↓
[Risk Debate] → Loop with aggressive/conservative/neutral perspectives
  - Aggressive debater
  - Conservative debater
  - Neutral debater
  - Judge → RiskAssessment
  ↓
[Portfolio Manager] → Final decision with account context
  ↓
[Execute/Log]
  - If IBKR enabled & auto_execute: Place order
  - Persist decision to memory log
  - Write report to disk
  ↓
END
```

### Conditional Logic (Routers)

```python
# From conditional_logic.py
class ConditionalLogic:
    def should_continue_debate(self, state, max_rounds=3):
        """Decide if debate should continue or move to judgment"""
        if state['debate_state']['count'] >= max_rounds:
            return "judge"  # Router to judge node
        return "next_speaker"  # Continue debate
    
    def route_after_trader(self, state):
        """Route based on trader decision"""
        action = extract_action_from_trader_output(state)
        if action == "skip":
            return "end"
        return "risk_debate"
```

---

## LLM Integration

### Provider Architecture

Multi-provider support through factory pattern:

```
BaseClient (Abstract)
├── AnthropicClient (Claude models)
├── OpenAIClient (GPT, compatible endpoints)
├── GoogleClient (Gemini, Gemini Thinking)
├── BedrockClient (AWS Bedrock)
├── AzureOpenAIClient (Azure)
└── (etc.)
```

### Client Creation

```python
# From llm_clients/factory.py
def create_llm_client(provider, model, **kwargs):
    clients = {
        "anthropic": AnthropicClient,
        "openai": OpenAIClient,
        "google": GoogleClient,
        "bedrock": BedrockClient,
        ...
    }
    client_class = clients[provider]
    return client_class(model, **kwargs)
```

### Model Capabilities Registry

```python
# From llm_clients/capabilities.py
MODEL_CAPABILITIES = {
    "gpt-5.6": {
        "supports_tool_choice": True,
        "supports_json_schema": True,
        "supports_reasoning": False,  # Non-reasoning model
        "max_tokens": 128000,
    },
    "claude-opus-5": {
        "supports_tool_choice": True,
        "supports_vision": True,
        "supports_cache": True,
        "max_tokens": 200000,
    },
    "deepseek-v3": {
        "supports_tool_choice": False,  # Must use tool_use
        "supports_thinking": True,
        "max_tokens": 8192,
    },
}
```

### Tool Binding & Execution

Each agent binds its tools to the LLM:

```python
# In agent creation
llm_with_tools = llm_client.bind_tools([
    get_stock_data,
    get_indicators,
    get_news,
    ...
])

# LLM returns tool_calls
response = llm_with_tools.invoke(prompt)

# Tool execution loop (in agent)
while response.tool_calls:
    for tool_call in response.tool_calls:
        result = tools[tool_call.name](**tool_call.args)
        response = llm.invoke(update_with_tool_result(response, result))
```

### Structured Output

Three decision-making agents use provider-native structured output:

```python
# OpenAI: json_schema
llm_with_structure = llm.with_structured_output(ResearchPlan, method="json_schema")

# Anthropic: tool-use with parsing
llm_with_structure = llm.with_structured_output(ResearchPlan, method="tool")

# Gemini: response_schema
llm_with_structure = llm.with_structured_output(ResearchPlan, method="json_schema")
```

### Model Selection

```python
# Configuration defines two models:
config = {
    "deep_think_llm": "gpt-5.6",        # Complex reasoning (Trader, Portfolio Manager)
    "quick_think_llm": "gpt-5.6-luna",  # Fast decisions (Analysts, Debaters)
}

# Agents instantiated with appropriate model
trader = Trader(llm_client=create_llm_client("openai", "gpt-5.6"))
analyst = MarketAnalyst(llm_client=create_llm_client("openai", "gpt-5.6-luna"))
```

### Retry Logic & Rate Limiting

```python
# Configuration
llm_max_retries = 3  # Retry budget
timeout_seconds = 60

# Automatic retry on transient errors
for attempt in range(llm_max_retries):
    try:
        response = llm.invoke(prompt)
        return response
    except (RateLimitError, TimeoutError) as e:
        if attempt < llm_max_retries - 1:
            wait_time = 2 ** attempt + random.uniform(0, 1)
            await asyncio.sleep(wait_time)
        else:
            raise
```

---

## Decision Making Process

### 1. Research Manager Logic

```python
# Input: Analyst reports (market_report, fundamentals_report, etc.)
# Input: Investment debate outcome
# Output: ResearchPlan (structured)

prompt = f"""
You are a research manager. Synthesize the following analyses:

{market_report}
{fundamentals_report}
{sentiment_report}
{news_report}

The investment debate concluded: {judge_decision}

Provide your investment recommendation:
1. Recommendation (Buy/Overweight/Hold/Underweight/Sell)
2. Rationale (detailed reasoning)
3. Strategic Actions (concrete trading steps)
4. Confidence Level (1-5)
"""

plan = llm.with_structured_output(ResearchPlan).invoke(prompt)
```

### 2. Trader Logic

```python
# Simple translation: 5-tier → 3-tier
# Input: ResearchPlan with recommendation
# Output: TraderAction

mapper = {
    "Buy": "Buy",
    "Overweight": "Buy",
    "Hold": "Hold",
    "Underweight": "Sell",
    "Sell": "Sell",
}

action = mapper[plan.recommendation]
```

### 3. Portfolio Manager Logic

```python
# Final gate-keeping decision
# Input: TraderAction + Risk assessment + Account context
# Output: PortfolioRating + Execution signal

prompt = f"""
Portfolio Manager Decision:

Trader Action: {trader_action}
Risk Assessment: {risk_assessment}
Account Context: {account_context}

Position limits: ${position_limit}
Current portfolio: {current_positions}

Final recommendation considering risk and account limits?
"""

decision = llm.with_structured_output(PortfolioRating).invoke(prompt)

# Execution gate
if decision == "Buy" and can_execute:
    execute_order("BUY", ticker, size)
elif decision == "Sell" and can_execute:
    execute_order("SELL", ticker, size)
# else: Hold, do nothing
```

### 4. Debate Mechanics

#### Investment Debate (Bull vs Bear)

```python
# Max rounds: max_debate_rounds (default 3)
# Stopping conditions:
#   1. Reached max rounds
#   2. Explicit consensus detected
#   3. Judge confidence threshold met

debate_flow = [
    ("bull_researcher", "Present bullish thesis"),
    ("bear_researcher", "Respond to bull argument"),
    ("bull_researcher", "Counter-respond to bear"),
    # Continue alternating until max_rounds
]

# Judge synthesis
judge_prompt = f"""
Bull Position: {bull_history}
Bear Position: {bear_history}

Synthesize both perspectives into a unified investment recommendation.
Resolution: [Consensus or decision on disagreement]
"""

judge_decision = judge.invoke(judge_prompt)
```

#### Risk Debate (Aggressive vs Conservative vs Neutral)

```python
# Similar structure but 3-way debate
# Aggressive: "We should size up, accept the risk"
# Conservative: "We should size down, protect capital"
# Neutral: "Balanced risk-reward"

# Judge synthesis considers:
# - Account liquidation value
# - Position limits
# - Volatility regime
# - Portfolio correlation

risk_decision = judge.invoke(f"""
Account Size: ${account_nlv}
Volatility (VIX): {current_vix}
Existing Positions: {positions}

Aggressive opinion: {aggressive_opinion}
Conservative opinion: {conservative_opinion}
Neutral opinion: {neutral_opinion}

What's the risk-appropriate sizing?
""")
```

---

## Persistence & Recovery

### 1. Decision Memory Log

**Path**: `~/.tradingagents/memory/trading_memory.md`

**Structure**:
```markdown
# Trading Decision Log

## 2026-01-15 | NVDA | $120.45
**Decision**: Buy
**Confidence**: 4/5
**Rationale**: Strong fundamentals + positive technical setup

### Analyst Summary
- Market: Bullish setup (MACD positive crossover)
- Fundamentals: Revenue beat, margin expansion
- Sentiment: Positive retail interest
- News: Positive AI catalyst

### Realized Return
- Entry: $120.45
- Current: $125.30
- Return: +4.0%
- Alpha vs SPY: +1.2%

### Reflection
Strong conviction thesis played out well. RSI showed room to run. Consider similar patterns in software sector.

---
```

**Reflection Integration**:
```python
# Before running analysis, fetch recent same-ticker decisions
past_context = memory_log.get_recent_decisions("NVDA")
# Generate reflection
reflection = reflector.generate_reflection(past_decision, realized_return)
# Inject into Portfolio Manager prompt
state["past_context"] = reflection
```

### 2. Checkpoint Resume

**Technology**: LangGraph checkpointer with SQLite backend

**Path**: `~/.tradingagents/cache/checkpoints/<TICKER>.db`

**State Saved After Each Node**:
```
Step 1: START → instrument_context resolved
Step 2: Data acquisition complete
Step 3: Market analyst complete
Step 4: Social analyst complete
Step 5: News analyst complete
Step 6: Fundamentals analyst complete
Step 7: Investment debate round 1
Step 8: Investment debate round 2
Step 9: Research manager complete
Step 10: Trader complete
Step 11: Risk debate round 1
Step 12: Portfolio manager complete
Step 13: Execution complete
```

**Resume Mechanism**:
```python
if checkpoint_enabled:
    thread_id = get_thread_id(ticker, date)
    checkpointer = get_checkpointer(db_path)
    
    # Check if previous run exists
    if checkpointer.has_checkpoint(thread_id):
        print(f"Resuming from step {last_step}")
        state = checkpointer.load(thread_id)
    else:
        print("Starting fresh")
        state = create_initial_state()

graph.invoke(state, config={"configurable": {"thread_id": thread_id}})
```

**Cleanup**:
- On successful completion: Checkpoint deleted
- On error: Checkpoint retained for resume
- CLI option `--clear-checkpoints`: Force reset all

---

## Broker Integration

### Interactive Brokers (IBKR) Connection

**Three Independent Features**:

1. **Account Context** (Market Data)
   - Read-only: Net liquidation value, cash, positions
   - Enabled by: `TRADINGAGENTS_IBKR_ENABLED=true`
   - Used by: Trader and Portfolio Manager

2. **Market Data** (Alternative to yfinance)
   - Real-time stock quotes via IBKR API
   - Enabled by: `data_vendors.core_stock_apis = ["ibkr"]`
   - Fallback: yfinance if IBKR unavailable

3. **Order Execution** (Auto Trading)
   - Submit market or limit orders
   - Requires: `TRADINGAGENTS_IBKR_AUTO_EXECUTE=true`
   - Safety: Separate flag for live trading

### Account Context Flow

```python
# From brokers/context.py
def build_ibkr_account_context(ibkr_client):
    """
    Returns formatted account summary for agent prompts
    """
    if not ibkr_enabled:
        return ""  # Optional, agents continue without it
    
    account_data = ibkr_client.get_account_summary()
    return f"""
Account Context:
- Net Liquidation Value: ${account_data['NetLiquidation']}
- Available Cash: ${account_data['CashBalance']}
- Buying Power: ${account_data['BuyingPower']}
- Current Position ({ticker}): {current_shares} @ ${avg_cost}
- P&L: ${current_pnl} ({current_pnl_pct}%)
"""
```

### Order Execution Flow

```python
# From brokers/execution.py
def execute_decision(portfolio_decision, ticker, account_context, ibkr_config):
    if not ibkr_auto_execute:
        logger.info(f"Would execute {portfolio_decision} on {ticker} (auto_execute disabled)")
        return "logged"
    
    if portfolio_decision == "Hold":
        return "no_action"  # Don't place order
    
    # Check live trading gate
    if not ibkr_config['ibkr_paper'] and not os.getenv('TRADINGAGENTS_IBKR_CONFIRM_LIVE'):
        raise RuntimeError("Live trading requires TRADINGAGENTS_IBKR_CONFIRM_LIVE=true")
    
    # Place order
    ibkr_client.place_order(
        ticker=ticker,
        action=portfolio_decision,  # BUY/SELL/Hold
        order_type="market",
        account_id=account_context['account_id']
    )
    
    return "executed"
```

---

## Technical Implementation Details

### 1. Agent Creation Pattern

Each agent follows a template:

```python
from langgraph.prebuilt import create_react_agent

def create_market_analyst(llm_client):
    tools = [
        get_stock_data,
        get_indicators,
        get_verified_market_snapshot,
    ]
    
    system_prompt = """
You are a technical analysis expert. Analyze price action, volume, and indicators.
Focus on: MACD crossovers, RSI extremes, support/resistance, trend confirmation.
Provide objective observations with confidence levels.
    """
    
    return create_react_agent(
        llm_client,
        tools=tools,
        system_prompt=system_prompt,
    )

# Invoke agent
market_analyst = create_market_analyst(llm_client)
result = market_analyst.invoke({
    "messages": [("human", f"Analyze {ticker} for {trade_date}")],
    "market_report": "",  # Will be filled
})
```

### 2. Tool Implementation

Tools are decorated functions that agents can call:

```python
@tool
def get_stock_data(ticker: str, start_date: str, end_date: str) -> str:
    """
    Retrieve daily OHLCV data for a stock.
    
    Args:
        ticker: Stock ticker symbol
        start_date: YYYY-MM-DD format
        end_date: YYYY-MM-DD format
    
    Returns:
        CSV string with OHLCV data
    """
    df = yf.download(ticker, start=start_date, end=end_date)
    return df.to_csv()

# Tool is auto-callable by agents via LLM tool-calling
```

### 3. LLM Client Interface

All LLM clients implement common interface:

```python
class BaseClient(ABC):
    def __init__(self, model, **kwargs):
        self.model = model
        self.temperature = kwargs.get('temperature', 0.7)
        self.max_tokens = kwargs.get('max_tokens', 8000)
    
    def invoke(self, messages, tools=None, **kwargs):
        """Send messages to LLM, return response"""
        pass
    
    def bind_tools(self, tools):
        """Bind tools to this LLM"""
        pass
    
    def with_structured_output(self, schema, method="auto"):
        """Return client configured for structured output"""
        pass
```

### 4. State Annotation (LangGraph)

Type-safe state management:

```python
from langgraph.graph import MessagesState

class AgentState(MessagesState):
    company_of_interest: str
    trade_date: str
    market_report: str
    fundamentals_report: str
    sentiment_report: str
    news_report: str
    investment_debate_state: InvestDebateState
    risk_debate_state: RiskDebateState
```

### 5. Configuration Management

Hierarchical configuration override:

```python
# Priority (highest to lowest):
# 1. Runtime config argument
# 2. Environment variables (TRADINGAGENTS_*)
# 3. .env file
# 4. Default config (default_config.py)

# Example:
config = DEFAULT_CONFIG.copy()  # Start with defaults

if os.getenv('TRADINGAGENTS_LLM_PROVIDER'):
    config['llm_provider'] = os.getenv('TRADINGAGENTS_LLM_PROVIDER')

if user_selected_provider:  # From CLI
    config['llm_provider'] = user_selected_provider
```

### 6. Logging & Debugging

```python
import logging

logger = logging.getLogger(__name__)

# Debug mode (CLI --debug)
if debug_mode:
    logging.basicConfig(level=logging.DEBUG)
    logger.debug(f"Initial state: {state}")
    logger.debug(f"Analyst reports: {reports}")

# Stats tracking for callbacks
stats_handler = StatsCallbackHandler()
# Tracks: LLM call count, tokens used, tool invocations
```

### 7. Error Handling & Resilience

```python
# Structured try-catch at tool level
def safe_tool_call(tool_func, *args, **kwargs):
    try:
        result = tool_func(*args, **kwargs)
        return result
    except RateLimitError as e:
        logger.warning(f"Rate limited: {e}. Retrying...")
        time.sleep(2 ** attempt)  # Exponential backoff
    except ValidationError as e:
        logger.error(f"Invalid data: {e}")
        return "Data unavailable"  # Graceful degradation
    except Exception as e:
        logger.error(f"Unexpected error in {tool_func.__name__}: {e}")
        raise  # Let agent handle or checkpoint retry

# At graph level: checkpoint saves state before risky operations
```

---

## Execution Summary

### Complete Execution Flow (Step by Step)

```
1. CLI User Input
   ↓
2. Ticker validation & resolution
   ↓
3. TradingAgentsGraph initialization
   - Load config
   - Create LLM clients
   - Initialize data vendors
   ↓
4. Data Acquisition
   - Fetch stock data (yfinance/Alpha Vantage/IBKR)
   - Fetch fundamentals (Alpha Vantage)
   - Fetch technical indicators (StockStats)
   - Fetch news (yfinance/Alpha Vantage)
   - Fetch sentiment (Reddit/StockTwits)
   - Fetch macro data (FRED)
   - Fetch account context (IBKR if enabled)
   ↓
5. Initial State Creation
   - Set company_of_interest
   - Set trade_date
   - Set all data reports
   - Initialize debate states
   ↓
6. Analyst Execution (Parallel or Sequential)
   Market Analyst → technicals
   Social Analyst → sentiment
   News Analyst → news impact
   Fundamentals Analyst → valuation
   ↓
7. Investment Debate (Bull vs Bear)
   - Bull makes case
   - Bear responds (if continue)
   - Bull counters (if continue)
   - Judge synthesizes → ResearchPlan
   ↓
8. Research Manager
   - Reads all reports
   - Reads investment debate outcome
   - Produces structured ResearchPlan
   ↓
9. Trader
   - Reads ResearchPlan
   - Maps 5-tier to 3-tier
   - Produces TraderAction
   ↓
10. Risk Debate (Aggressive vs Conservative vs Neutral)
    - Aggressive case
    - Conservative case
    - Neutral case
    - Judge → Risk assessment
    ↓
11. Portfolio Manager
    - Reads trader action + risk assessment
    - Reads account context
    - Produces final PortfolioRating
    ↓
12. Execution & Persistence
    - If IBKR enabled & auto_execute: Place order
    - Save decision to memory log
    - Write markdown report
    - Clear checkpoint (if successful)
    ↓
13. Display Results
    - Show decision to user
    - Show reasoning path
    - Show report structure
    ↓
END
```

---

## Configuration File Locations

```
~/.tradingagents/
├── memory/
│   └── trading_memory.md          # Decision log
├── cache/
│   └── checkpoints/
│       ├── AAPL.db                # Checkpoint DB per ticker
│       ├── NVDA.db
│       └── ...
└── reports/
    └── [auto-generated markdown reports]
```

---

## Key Design Decisions

| Decision | Rationale | Tradeoff |
|----------|-----------|----------|
| Multi-provider LLM support | Flexibility, cost optimization | Complexity in capability registry |
| Parallel analyst execution | Speed, independence of analysis | State management overhead |
| Debate-based reasoning | Reduces bias, improves consensus | Longer execution time |
| Structured output for decisions | Parsing reliability, consistent schema | Model may struggle with complex reasoning |
| Checkpoint persistence | Resume capability, fault tolerance | Storage overhead per run |
| No persistent cache | Always-fresh data avoids staleness | More API calls, rate limit risk |
| Point-in-time data validation | Prevents look-ahead bias | Alpha Vantage filtering complexity |
| Account context optional | Works without broker | Agents have less context |

---

## Performance Characteristics

### Typical Execution Times

| Component | Time | Factors |
|-----------|------|---------|
| Data acquisition | 15-45s | API rate limits, data size |
| Analyst parallel execution | 30-90s | Model speed, debate rounds |
| Investment debate | 30-90s | Max rounds, model reasoning |
| Trader + Portfolio Manager | 20-40s | Account context check |
| **Total** | **2-4 minutes** | Highly model dependent |

### Token Usage

| Agent | Avg Input Tokens | Avg Output Tokens |
|-------|------------------|-------------------|
| Market Analyst | 3,000-8,000 | 1,000-3,000 |
| Fundamentals Analyst | 4,000-10,000 | 1,000-3,000 |
| Sentiment Analyst | 2,000-5,000 | 500-2,000 |
| News Analyst | 3,000-7,000 | 1,000-3,000 |
| Debate Rounds (3) | 2,000-4,000 each | 500-2,000 each |
| Portfolio Manager | 3,000-6,000 | 500-1,500 |

### Scaling Characteristics

- **Linear** with number of analysts (parallel execution)
- **Linear** with debate rounds
- **Logarithmic** with data window (weekly vs monthly vs yearly)
- **Constant** with number of tools (LLM selects what to use)

---

## Testing Strategy

### Test Categories

1. **Unit Tests** (650+)
   - Individual data vendor parsing
   - Tool output validation
   - Schema parsing correctness
   - State transitions

2. **Integration Tests**
   - Full graph execution (with mock LLM)
   - Checkpoint save/restore
   - Multi-provider LLM switching
   - Debate mechanics

3. **Smoke Tests**
   - Quick sanity checks
   - CLI invocation
   - Report generation

### Running Tests

```bash
# All tests
pytest tests -v

# Specific marker
pytest tests -m "unit" -v
pytest tests -m "integration" -v
pytest tests -m "smoke" -v

# Coverage
pytest tests --cov=tradingagents
```

---

## Future Extensions

1. **Multi-stock portfolio analysis** - Correlation analysis across holdings
2. **Alternative data** - Satellite imagery, credit card data, etc.
3. **Custom agents** - User-defined specialized roles
4. **Live model fine-tuning** - Learn from realized returns
5. **Multi-timeframe analysis** - Intraday + daily + weekly reasoning
6. **Options strategy** - Leverage derivative instruments
7. **International markets** - Non-USD currency handling

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-15  
**Framework Version**: 0.4.0+

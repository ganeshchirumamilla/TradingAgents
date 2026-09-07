# IB Gateway Concurrency Model - Deep Dive

## Executive Summary

Our current implementation uses a **three-layer concurrency model**:
1. **IB Client Pool** (Queue-based, 3 connections)
2. **Timeframe Parallel Executor** (ThreadPoolExecutor, 3 workers)
3. **Chunk Parallel Executor** (ThreadPoolExecutor, 3 workers per timeframe)

This creates a potential **9x concurrency multiplier** that exceeds IB Gateway's comfortable limits.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│ MarketDataDownloaderV2.run(num_workers=3)                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ IB Client Pool (Queue-based)                         │   │
│  │ max_clients = 3                                      │   │
│  │ - Client 2000 (2026-09-06 17:20:18)                 │   │
│  │ - Client 2001 (2026-09-06 17:20:18)                 │   │
│  │ - Client 2002 (2026-09-06 17:20:18)                 │   │
│  │                                                      │   │
│  │ Each gets UNIQUE clientId to avoid conflicts         │   │
│  │ All connect to: 127.0.0.1:4002 (IB Gateway)        │   │
│  └──────────────────────────────────────────────────────┘   │
│           ↓                                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Timeframe Executor (ThreadPoolExecutor)              │   │
│  │ max_workers = 3                                      │   │
│  │                                                      │   │
│  │  Worker 1 → [DAILY]    Generates & downloads chunks │   │
│  │  Worker 2 → [HOURLY]   Generates & downloads chunks │   │
│  │  Worker 3 → [5MIN]     Generates & downloads chunks │   │
│  │  (blocked) → [1MIN]    Waits for worker availability│   │
│  └──────────────────────────────────────────────────────┘   │
│           ↓                                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Chunk Executor (Inside each timeframe worker)        │   │
│  │ max_workers = 3 (INHERITED from parent)              │   │
│  │                                                      │   │
│  │  Each timeframe spawns its OWN ThreadPoolExecutor    │   │
│  │  with max_workers=3                                  │   │
│  │                                                      │   │
│  │  [DAILY] spawns 3 workers to download daily chunks   │   │
│  │  [HOURLY] spawns 3 workers to download hourly chunks│   │
│  │  [5MIN] spawns 3 workers to download 5min chunks     │   │
│  │                                                      │   │
│  │  Problem: These inherit the SAME executor object!    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Connection Configuration

### IB Client Pool Setup

**File**: `download_market_data_v2.py`, lines 31-81

```python
class IBClientPool:
    def __init__(self, host: str, port: int, max_clients: int = 5):
        self.max_clients = max_clients                           # Default: 3
        self.available_clients = Queue(maxsize=max_clients)      # Thread-safe queue
        
        for i in range(max_clients):
            # Create unique client IDs
            client_id = 2000 + i + int(time.time()) % 1000
            ib = IB()
            ib.connect(host, port, clientId=client_id)
            self.available_clients.put((i, ib), timeout=2)
```

### Configuration Parameters

| Parameter | Value | Location | Purpose |
|-----------|-------|----------|---------|
| `max_clients` | 3 | Line 497 | IB Client Pool size |
| `num_workers` (Timeframe) | 3 | Line 503 | Timeframe-level parallelism |
| `max_workers` (Chunk) | 3 | Inherited | Chunk-level parallelism |
| `host` | 127.0.0.1 | Line 94 | IB Gateway host |
| `port` | 4002 | Line 95 | IB Gateway port |
| `clientId` base | 2000 | Line 46 | Base for unique IDs |

---

## Execution Flow

### Step 1: Initialization
```python
downloader = MarketDataDownloaderV2(ticker="AAPL")
downloader.run(num_workers=3)
```

**Actions:**
1. Create IBClientPool with 3 clients (all connecting to IB Gateway)
2. Each client gets UNIQUE clientId (2000+, 2001+, 2002+)
3. All 3 clients connect simultaneously to port 4002

**Concurrency Level: 3 IB connections established**

---

### Step 2: Timeframe Parallelization
```python
with ThreadPoolExecutor(max_workers=3) as executor:
    for timeframe in ['daily', 'hourly', '5min', '1min']:
        future = executor.submit(self.process_timeframe, timeframe, executor)
```

**Actions:**
1. Launch 4 timeframe tasks with 3 worker threads
2. First 3 tasks run in parallel (daily, hourly, 5min)
3. 4th task (1min) queues, waits for first worker to finish
4. **Each timeframe receives the SAME executor object**

**Concurrency Level: 3 timeframes executing in parallel**

---

### Step 3: Chunk Parallelization (PROBLEM!)
```python
def process_timeframe(self, timeframe: str, executor: ThreadPoolExecutor) -> dict:
    # executor is PASSED IN from the parent level!
    with executor:  # BUG: Reusing parent executor instead of new one
        for future in as_completed(futures):
            ...
```

**The Critical Issue:**
- Line 506: `executor.submit(self.process_timeframe, timeframe, executor)`
- The SAME ThreadPoolExecutor is passed to each timeframe
- Inside process_timeframe (line 440), it receives this executor
- Each timeframe's chunks use this shared executor
- **Result: 3 timeframes × 3 workers = potential 9 concurrent threads**

---

## Concurrency Multiplier Effect

### Theoretical Maximum Concurrency

```
Layer 1: IB Client Pool
  └─ 3 fixed connections to IB Gateway

Layer 2: Timeframe Workers
  └─ 3 concurrent timeframes (daily, hourly, 5min)
  
Layer 3: Chunk Workers (per timeframe)
  └─ 3 concurrent chunks per timeframe
  
TOTAL POTENTIAL CONCURRENCY:
  - Simultaneous IB requests: 3 (from Pool)
  - Simultaneous threads: 3 (timeframes) + (3 × 3 chunks) = 12 threads
  - **Effective concurrency: 3 IB clients / 12 requesting threads = CONTENTION**
```

### What Actually Happens

```
Time T=0:
  [DAILY]   - Worker 1: Request chunk 1 (uses Client A)
  [HOURLY]  - Worker 2: Request chunk 1 (uses Client B)
  [5MIN]    - Worker 3: Request chunk 1 (uses Client C)

Time T=1:
  [DAILY]   - Worker 1: Waiting for response
  [DAILY]   - Worker 2: Request chunk 2 (BLOCKED - no clients available)
  [DAILY]   - Worker 3: Request chunk 3 (BLOCKED - no clients available)
  [HOURLY]  - Worker X: Request chunk 2 (BLOCKED - no clients available)
  [5MIN]    - Worker Y: Request chunk 2 (BLOCKED - no clients available)

Result:
  - 3 requests in flight (using all 3 clients)
  - 9+ threads waiting for a client
  - IB Gateway gets overwhelmed with queued requests
  - Timeout: "Unable to connect as the client id is already in use"
```

---

## Why IB Gateway Struggles

### IB Gateway Connection Limits

**Default Limits:**
- **Max connections per session**: ~1-2 (without special config)
- **Max API clients**: 5-10 (but with performance degradation)
- **Request queue depth**: Limited
- **Thread pool on IB side**: May not scale well

### Our Current Load

```
IB Gateway Load Analysis:
├─ Number of connections: 3
├─ Simultaneous requests/connection: 3-4 (across threads)
├─ Total threads hitting IB API: 12 potential
└─ Result: OVERLOAD
```

---

## The Queue.get() Bottleneck

### Client Acquisition

```python
def get_client(self, timeout: int = 5) -> Optional[Tuple[int, IB]]:
    try:
        client_id, ib = self.available_clients.get(timeout=timeout)
        return client_id, ib
    except:
        return None  # TIMEOUT: No client available within 5 seconds
```

**What Happens:**
1. Thread wants to download chunk → calls `get_client()`
2. Queue is empty (all 3 clients in use)
3. Thread waits 5 seconds
4. **If client not returned in 5s → Returns None → Download fails**

---

## Recommended Concurrency Model

### Option 1: Reduce Parallelism (Safest)

```python
# Change from:
downloader.run(num_workers=3)

# To:
downloader.run(num_workers=1)  # Sequential timeframes
```

**Result:**
- Only 1 IB client active at a time
- Only 1 timeframe downloads at a time
- Slower but reliable

---

### Option 2: Proper Client Pool Management

```python
# Current (WRONG):
executor.submit(self.process_timeframe, timeframe, executor)

# Correct:
executor.submit(self.process_timeframe, timeframe)  # Don't pass executor

# Inside process_timeframe:
def process_timeframe(self, timeframe: str):
    # Request client from pool for each chunk
    client = self.client_pool.get_client()  # One at a time
    try:
        # Download chunk
        ...
    finally:
        self.client_pool.return_client(client)
```

**Result:**
- IB clients properly serialized per chunk
- Max 3 concurrent downloads total
- Better thread safety

---

### Option 3: Adaptive Concurrency

```python
# Create separate executor per timeframe
for timeframe in timeframes:
    local_executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        self.process_timeframe, 
        timeframe, 
        local_executor  # Each timeframe gets its own executor
    )
```

**Result:**
- 3 timeframes run in parallel
- Each has 1 worker (using 1 client from pool)
- **Max 3 concurrent IB requests** (one per client)

---

## Current Implementation Summary

| Aspect | Configuration |
|--------|---------------|
| **IB Clients** | 3 (Pool) |
| **Timeframe Workers** | 3 (Executor) |
| **Chunk Workers** | 3 per timeframe (Inherited executor) |
| **Max Threads** | 12+ |
| **Max IB Connections** | 3 |
| **Thread-to-Connection Ratio** | 4:1 (12 threads : 3 connections) |
| **IB Gateway Health** | ⚠️ STRESSED |

---

## Why V1 Works Better

**V1 (download_market_data.py):**
- Sequential downloads per timeframe
- Single IB client throughout
- No client pool complexity
- Simple: 1 thread → 1 client → 1 request at a time

**Result: Stable, predictable, slower but reliable**

---

## Recommendations

### Short Term
✅ Use **V1 (download_market_data.py)** for production
- Single-threaded, proven reliable
- No IB Gateway contention
- Adequate performance

### Medium Term
✅ Tune V2 configuration
```bash
# Try:
python download_market_data_v2.py AAPL 1  # Num_workers=1
```

### Long Term
✅ Refactor V2 concurrency model
- Use proper client pool serialization
- Create per-timeframe executors with reduced workers
- Add backpressure handling

---

## Connection String Configuration

### Current Setup
```
IB Gateway: 127.0.0.1:4002
Protocol:   ib_async (asyncio-based)
Clients:    3 (named: 2000, 2001, 2002 + timestamp salt)
Max per client: Not throttled (causes contention)
```

### Ideal Setup
```
IB Gateway: 127.0.0.1:4002
Protocol:   ib_async (asyncio-based)
Clients:    3 (one per timeframe effectively)
Max per client: 1 (sequential requests)
Queue depth: 10 (reasonable buffer)
Timeout: 30s (allow for network latency)
```

---

## Debugging Commands

### Check IB Gateway Logs
```bash
# On Windows:
tail -f "C:\TWS API\logs\*.log"

# On Mac/Linux:
tail -f ~/Jts/jts*/*.log
```

### Monitor Connections
```bash
# Check active connections to port 4002
netstat -an | grep 4002

# On Mac:
lsof -i :4002
```

### Test Single Client
```python
from ib_async import IB, Stock, util

ib = IB()
ib.connect('127.0.0.1', 4002, clientId=9999)
contract = Stock('AAPL', 'SMART', 'USD')
bars = ib.reqHistoricalData(contract, '', '1 D', '1 day', 'TRADES', True, 1)
ib.disconnect()
print(f"Downloaded {len(bars)} bars with single client")
```

---

## Summary Table

| Model | Clients | Threads | Concurrency | IB Load | Reliability |
|-------|---------|---------|-------------|---------|-------------|
| **V1** | 1 | 1 | None | Low | ✅ High |
| **V2 (3x3x3)** | 3 | 12+ | High | High | ❌ Poor |
| **V2 (1x4)** | 3 | 4 | Medium | Medium | ✅ Good |
| **V2 (3x1)** | 3 | 3 | Low | Low | ✅ Very High |

**Recommendation: V1 for production, V2 tuned to (3x1) for scaling**

---

Generated: 2026-09-06

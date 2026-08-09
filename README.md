# Binance Futures Grid Trading Bot (Client-Server IPC Architecture)

A robust, production-grade automated grid trading bot optimized for the Binance Futures platform. The project is designed with a strictly decoupled Client-Server architecture utilizing low-latency Inter-Process Communication (IPC) via UNIX domain sockets (on Linux) or TCP loopback sockets (on Windows). 

The backend runs as a daemon managing real-time trade states, while an independent CLI tool allows full orchestration, runtime configuration, and telemetry inspection.

---

## System Architecture & Tech Stack
* **Core Language:** Python 
* **Architecture:** Decoupled Client-Server (Daemonized Engine + CLI Controller)
* **Inter-Process Communication (IPC):** UNIX Domain Sockets (`/tmp/*.sock`) & TCP Loopback Sockets
* **State Persistence:** Flat-file JSON State Management (Auto-recovery on process restart)
* **Integrations:** Binance Futures API (via standard REST/Websocket abstraction), Telegram Bot API

---

## Key Engineering Features

* **Advanced IPC Socket Control:** The bot engine creates a local socket listener bound to a specific trading pair (e.g., `gridbot_BTCUSDC.sock`). This allows independent, parallel engine instances to run simultaneously for different asset pairs on the same server.
* **Resilient Multithreaded Engine:** The active trading loop operates within dedicated background threads, separating heavy API request-response patterns and long-running order polling from the internal command listener.
* **Persistent State Management:** Real-time trade status, cycle steps, and position histories are synchronized into structured JSON state tracking files (`state/{SYMBOL}_active.json`). Upon an unexpected server reboot or daemon crash, the bot instantly reloads its state and automatically resumes target management.
* **Auto-Recovery Order Chaining:** Features an intelligent order-lifecycle tracker. It orchestrates initial entry limits, dynamic layer scaling (Grid step sizes), real-time leverage adjustments, liquidation boundary calculations, and adaptive multi-layered profit-taking.
* **Asynchronous Notifications:** Implements Telegram Bot API wrappers to push instantaneous execution, liquidation updates, cycle achievements, and performance metric logs out to telegram chat channels.

---

## CLI Client Commands & Telemetry Matrix

The `cli_client.py` utility establishes an interactive shell wrapper allowing real-time injection of parameters and diagnostic tracking into the background daemon. 

### Available Core Interface Commands:
* `run` – Initializes background trade tracking and order loops.
* `pause` / `resume` – Temporarily pauses or resumes trading logic execution.
* `stop` – Immediate emergency termination of the current strategy.
* `stop_at_end` – Flags the engine to cleanly shut down after the current grid cycle completes.
* `simulate` – Runs pre-flight mathematical modeling of grid levels, capital requirements, and margin limits based on current market conditions.
* `status` – Calculates and displays current net profit margins minus exchange execution fees.
* `balance` – Pulls current available stablecoin margins from the Binance Futures wallet.
* `open_orders` / `orderbook` – Telemetry dump of open contract levels directly from the exchange.
* `set_l` / `get_l` – Modifies or audits leverage scaling parameters in real-time.
* `likvidacna_cena` – Real-time computation of liquidation threat levels.
* `quit` – Safely closes the CLI shell interface.

---

## Repository Structure (Core Component Overview)

```text
├── config/                           # Static environment configurations
│   └── BTCUSDC.json                  # Grid parameters, steps, and leverage configuration
├── API/                              # Secure Environment Settings (Ignored in Git)
│   ├── API_keys.env                  # Binance Futures API connection keys
│   └── telegram.env                  # Telegram bot token and target chat ID
├── state/                            # Active persistent memories (Auto-generated)
│   ├── BTCUSDC_active.json           # Live state-machine tracker for the active grid cycle
│   └── cyklus_20260809_100200.json   # Immutable archival records of finalized grid cycles
├── main.py                           # Master Server Daemon (IPC Socket Server & Thread Manager)
├── cli_client.py                     # Interactive terminal CLI controller (Socket Client)
├── bot.py                            # Core GridBot Engine class (State, calculations & logic)
├── client_handler.py                 # Abstraction driver layer for Binance API orchestration
├── evaluation.py                     # Analytics utility for computing realized gains and trading fees
├── utils.py                          # Telegram integrations and mathematical utilities
└── README.md                         # Project documentation

```

---
## Environment Configuration (.env Templates)

For secure API communication, create an `API/` folder in the root directory containing the following two environment files.

### `API/API_keys.env`
```env
API_Key = your_binance_futures_api_key_here
Secret_Key = your_binance_futures_secret_key_here
```

### `API/telegram.env`
```env
CHAT_ID = your_telegram_chat_id_here
TOKEN = your_telegram_bot_auth_token_here
```

## Strategy Configuration (config/BTCUSDC.json)

The bot's mathematical grid model is driven by a centralized JSON configuration. Below is a production example of a defensive LONG strategy configuration for the `BTCUSDC` pair:

### Parameter Matrix Glossary:
* `direction` – Market bias configuration (`LONG` or `SHORT`).
* `leverage` – Margin multiplication factor applied on Binance Futures (e.g., `10x`).
* `order_count` – Total amount of grid safety layers/orders deployed in the pipeline.
* `step_up` / `step_down` – Percentage distance threshold between individual grid price levels (set to `0.9%`).
* `order_amount_stable` – Fixed margin size allocated per single grid order in stablecoins (`11 USDC`).
* `use_futures` – Boolean flag switching between spot trading and structural futures contracts.
* `num_of_cycles` – Hard ceiling cap to terminate operations after completing a fixed number of grid loops.
* `max_open_rice` – Critical circuit breaker (safety switch). The engine will reject opening new cycles if the market price exceeds this price threshold (`$160,000`).



## Deployment & Execution Guide

### 1. Ingesting and Running the Daemon (Server)
To start the trading engine for a specific market asset (e.g., `BTCUSDC`), execute the master file with the symbol parameter:

```bash
# Launch the core daemon for BTCUSDC (Defaults to BTCUSDC if omitted)
python main.py BTCUSDC
```

*The daemon will check for existing JSON active logs. If found, it instantly resumes the grid positions.*

### 2. Orchestrating the Bot via the Interactive Shell (Client)
In a separate terminal workspace or a persistent multiplexed session (such as `tmux`), boot up the command controller:

```bash
# Initialize the interactive CLI client
python cli_client.py

CLI pripraveny. Zadajte prikaz:
> simulate
[INFO] Simulovane levely:
1: {'price': 64386.5, 'qty': 0.002, 'notional': 128.77, 'margin': 18.4, 'fee': 0.1288}
2: {'price': 63935.8, 'qty': 0.002, 'notional': 127.87, 'margin': 18.27, 'fee': 0.1279}
...
Direction: LONG
Aktualna cena: 68720.5
Zostatok Futures ucet: 550.0 USDC
Percentualny rozsah cez vsetky levely: 4.5 %

> run
Obchodovanie spustene na pozadi.

> stop
[BOT] Obchodovanie bolo vypnute.

```

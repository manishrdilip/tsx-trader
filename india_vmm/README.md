# India VMM bot (NSE, Zerodha Kite)

Momentum (VMM) bot for NSE delivery stocks, modelled on the Canada bot in `vmm_bot/`.
Status: **dry run only.** It places no orders until you pass `--live` and set `TRADING_ENABLED=true`.

## Rules (as built)

| Item | Rule |
|---|---|
| Universe | NSE `.NS` stocks. Drops indices, ETFs (names ending `BEES`, `ETF`, `SGB…`, `LIQUID`). |
| Price band | Rs 60 to Rs 6,000 |
| Liquidity | 20-day median of close x volume >= Rs 50 lakh |
| History | >= 253 completed sessions |
| Market filter | NIFTYBEES.NS (fallback ^NSEI) close above its 200-day average. If not, **no new buys**. Sells still run. |
| Buy | 12-month return in the top 10% of the universe AND close above 200-day average. Ranked by 12m return / 126-day volatility (risk-adjusted), best first. `INDIA_VMM_RANK=r12` = old plain ranking. |
| Sell | close below 200-day average, OR 12-month return below the top-40% cut. |
| Slots | `clamp(equity // Rs 10,000, 10, 20)`: 10 slots below Rs 2 lakh, 20 from Rs 2 lakh (as backtested). |
| Per-order cap | 15% of equity (`INDIA_VMM_MAX_ORDER_PCT`). |
| Orders per run | 25 max |
| Order type | LIMIT, CNC (delivery), DAY |
| Buy limit | last close x 1.01, rounded up to Rs 0.05 |
| Sell limit | last close x 0.97, rounded down to Rs 0.05 |
| Duplicates | no second order for a symbol that already has an open order today |
| Protected | NIFTYBEES and ^NSEI, plus `INDIA_VMM_PROTECTED`. Never traded. |
| Ledger | the bot sells only shares it bought (or that you adopt in `INDIA_VMM_ADOPT`). Other holdings are untouched. |

## Files

- `rules.py`: pure rules (signals, plan). No network, no broker. Unit-tested.
- `data.py`: price loaders. Offline: a parquet file. Live: yfinance `.NS` bars (free).
- `broker.py`: the only file that talks to Kite.
- `run.py`: the runner. Reconciles the ledger, plans, places orders only when live, and writes `results/india_vmm/` (state.json with ledger, pending and run_slots; report.md; log.jsonl; last_plan.json). Sends the plan to Telegram.
- `tests/test_rules.py`: 14 tests. Run `python -m unittest discover -s india_vmm/tests -v`.

## Setup

```
pip install -r india_vmm/requirements.txt
```

Secrets go in environment variables only, never in the repo or in chat:
`KITE_API_KEY`, `KITE_ACCESS_TOKEN` (same names as `india_laptop/`), and optionally `INDIA_VMM_BUDGET_INR`, `INDIA_VMM_ADOPT`, `INDIA_VMM_PROTECTED`.

## Running

```
# offline plan from a local NSE price file (no broker, no orders)
python india_vmm/run.py --parquet /path/to/prices.parquet --cash 2000

# plan against the Zerodha account (dry run)
python india_vmm/run.py

# place real orders (only after review and approval)
TRADING_ENABLED=true python india_vmm/run.py --live
```

## Before any live run

1. Kite Connect static IP: the machine that runs the bot must have its IP registered in the Kite developer console. Orders from an unregistered IP are refused.
2. Kite historical data needs the Connect plan (about Rs 500/month). Until then the live run uses yfinance, which is free but unofficial. Check its prices against Kite before trusting a live run.
3. Review `results/last_plan.json` and the notes. Confirm which holdings the bot should adopt. Groww and any other accounts are separate and are not touched.
4. Schedule: run after the 15:30 close for next-session orders, or before the 09:15 open for same-day DAY limits. Use the same timing as the Canada bot.

## Known limits

- Small accounts: at Rs 2,000 each slot is Rs 200, so only stocks priced under about Rs 200 can be bought. Most high-momentum names are skipped, with a note.
- Sell proceeds are not counted as buy cash (CNC sells settle T+1).
- The universe is wide (about 1,100 names pass the filters), and many top-momentum names are small and volatile. This is the same concern the lab backtests were checking.
- Momentum rules here are the tested rules from the lab. They are not a guarantee of future returns.

## Schedule (same pattern as the TSX bot)

Runs on the India laptop / server (Zerodha needs the registered static IP), Mon-Fri IST:
- **AM run 9:40** (backup 10:10): sells first, then buys with settled cash.
- **PM run 2:45** (backup 3:00): puts cash from settled sells back to work.
- Each slot runs once a day (`run_slots` in state.json); a backup run that finds the slot done exits.
- Signals use the previous completed session's close.
- Orders are placed only when `.env` has `TRADING_ENABLED=true`. Otherwise every run is a dry run and the plan goes to Telegram.
- `auto_trader.py monitor` skips the VMM bot's stocks (no GTT stop/target on them), so the two do not fight.

After pulling this change, run the setup once more (laptop: `setup.ps1`; server: `sudo bash india_server/setup.sh`) to add the two new scheduled jobs.

# VMM bot (Wealthsimple TFSA via SnapTrade)

Runs the locked VMM v1 rules every weekday morning (~9:40 ET) from GitHub Actions on ONE pinned
Wealthsimple TFSA. Signals use the previous close; orders are Day limit orders.

## Setup (repo Settings -> Secrets and variables -> Actions)
Secrets: `SNAPTRADE_CLIENT_ID`, `SNAPTRADE_CONSUMER_KEY` (optional: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`)
Variables:
| Name | Value | Meaning |
|---|---|---|
| `VMM_ACCOUNT_ID` | SnapTrade account ID of the dedicated VMM TFSA | the ONLY account the bot touches |
| `DRY_RUN` | `true` (default) | `false` to allow orders |
| `TRADING_ENABLED` | `false` (default) | kill switch; must be `true` to trade |
| `MAX_ORDER_CAD` | `800` | largest single buy allowed |
| `VMM_BUDGET_CAD` | e.g. `3000` | most money the bot may manage in a shared account (0 = whole account) |
| `VMM_PROTECTED` | `VEQT.TO,AIQ.TO,SPCX.TO,SPCX` | never bought or sold |
| `VMM_EXCLUDE` | `LCFS.TO,TWM.TO` | never bought (e.g. takeover targets) |

The bot keeps a ledger of shares it bought itself (`results/vmm_bot/state.json`) and only ever sells those.
Shares you hold manually in the same account are ignored and never doubled.

Orders are sent only when `DRY_RUN=false` AND `TRADING_ENABLED=true`. Set `TRADING_ENABLED=false` to stop instantly.

## Output
`results/vmm_bot/report.md` (latest), `log.jsonl` (every run), `state.json` (monthly split, saved after live runs only).

## 28% trailing rule (added 9 Nov 2026)
On top of the 200-day and top-40% sell rules, the bot sells a stock when its close is 28% below the highest
close since it started tracking it (`VMM_TRAIL_PCT`). After such a sale it buys the stock back only once the
price is 10% below the sale price and the normal buy rules hold (`VMM_REBUY_DROP_PCT`). Highs are kept in
`results/vmm_bot/state.json` (`peaks`, `rebuy_blocks`). Evidence: Stock project doc
`claude/vmm-exit-rules-grid-2026-11-09.md`. Set `VMM_TRAIL_PCT=0` to switch it off.

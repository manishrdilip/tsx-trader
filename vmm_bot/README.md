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

Orders are sent only when `DRY_RUN=false` AND `TRADING_ENABLED=true`. Set `TRADING_ENABLED=false` to stop instantly.

## Output
`results/vmm_bot/report.md` (latest), `log.jsonl` (every run), `state.json` (monthly split, saved after live runs only).

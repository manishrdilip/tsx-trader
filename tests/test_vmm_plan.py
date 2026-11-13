"""Offline tests for vmm_bot/plan.py: fake account, fake prices, no network.
Run: python -m pytest tests -q"""
import datetime as dt, importlib, json, os, sys
import numpy as np, pandas as pd, pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "vmm_bot"))
TODAY = dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).date()


def make_prices(n_stocks=30, crash=None, end=None):
    """300 business days ending the business day before today. Stock i trends up at a different speed."""
    end = end or (pd.Timestamp(TODAY) - pd.tseries.offsets.BDay(1))
    idx = pd.bdate_range(end=end, periods=300)
    cols = {}
    for i in range(n_stocks):
        cols[f"S{i:02d}.TO"] = 10 * np.exp(np.linspace(0, 0.02 * i, 300))
    cols["XIU.TO"] = 30 * np.exp(np.linspace(0, 0.2, 300))
    C = pd.DataFrame(cols, index=idx)
    if crash:
        for t, f in crash.items():
            C.loc[C.index[-1], t] = C[t].iloc[-2] * f
    V = pd.DataFrame(1_000_000, index=idx, columns=C.columns)
    return C, V


@pytest.fixture
def plan(monkeypatch, tmp_path):
    def load(env=None, prices=None, state=None, guard=None):
        for k, v in {"VMM_MODE": "daily", "VMM_MAX_SLOTS": "20", "VMM_ADOPT": "", "VMM_EXCLUDE": "",
                     "VMM_FUND_MAX_CAD": "0", "VMM_STATE_DIR": str(tmp_path), "RUN_SLOT": "AM", **(env or {})}.items():
            monkeypatch.setenv(k, v)
        sys.modules.pop("plan", None)
        p = importlib.import_module("plan")
        C, V = prices or make_prices()
        monkeypatch.setattr(p, "universe", lambda: [c for c in C.columns if c != "XIU.TO"])
        monkeypatch.setattr(p, "prices", lambda tick: (C, V))
        monkeypatch.setattr(p, "market_guard", lambda: list(guard or []))
        if state is not None:
            json.dump(state, open(tmp_path / "state.json", "w"))
        def run(positions, cash):
            snap = {"positions": [{"symbol": t.replace(".TO", ""), "units": u} for t, u in positions.items()],
                    "cash_cad": cash, "open_orders": []}
            json.dump(snap, open(tmp_path / "snap.json", "w"))
            p.main(str(tmp_path / "snap.json"), str(tmp_path / "plan.json"))
            return json.load(open(tmp_path / "plan.json"))
        return p, run
    return load


def buys(out): return [o for o in out["orders"] if o["action"] == "BUY"]
def sells(out): return {o["ticker"] for o in out["orders"] if o["action"] == "SELL"}


def test_buys_top_momentum_with_cash(plan):
    _, run = plan()
    out = run({}, 2000)
    assert buys(out) and all(o["ticker"] in {"S29.TO", "S28.TO", "S27.TO", "S26.TO", "S25.TO"} for o in buys(out)[:3])
    assert sum(o["units"] * o["limit"] for o in buys(out)) <= 2000 + 1


def test_never_touches_shares_it_did_not_buy(plan):
    _, run = plan()
    out = run({"S00.TO": 100, "VEQT.TO": 50}, 0)  # not in ledger, not adopted
    assert not sells(out)


def test_daily_sells_crashed_holding(plan):
    _, run = plan(prices=make_prices(crash={"S29.TO": 0.5}), state={"ledger": {"S29.TO": 10}})
    out = run({"S29.TO": 10}, 0)
    assert "S29.TO" in sells(out)


def test_slow_mode_trail_sells_even_in_min_hold(plan):
    st = {"ledger": {"S29.TO": 10}, "entry": {"S29.TO": TODAY.isoformat()}, "peaks": {"S29.TO": 1000.0}}
    _, run = plan(env={"VMM_MODE": "slow", "VMM_MAX_SLOTS": "8"}, state=st)
    assert "S29.TO" in sells(run({"S29.TO": 10}, 0))  # far below its 1000 peak -> 28% emergency sell


def test_slow_mode_waits_for_min_hold(plan):
    C, V = make_prices()
    C["S29.TO"] = C["S29.TO"].iloc[::-1].values  # falling stock: below its 200-day line, no trail (peak = today)
    st = {"ledger": {"S29.TO": 10}, "entry": {"S29.TO": TODAY.isoformat()}}
    _, run = plan(env={"VMM_MODE": "slow", "VMM_MAX_SLOTS": "8"}, prices=(C, V), state=st)
    out = run({"S29.TO": 10}, 0)
    assert "S29.TO" not in sells(out) and any("waits" in n for n in out["notes"])


def test_slow_mode_sells_after_min_hold_on_review(plan):
    C, V = make_prices()
    C["S29.TO"] = C["S29.TO"].iloc[::-1].values
    st = {"ledger": {"S29.TO": 10}, "entry": {"S29.TO": (TODAY - dt.timedelta(days=120)).isoformat()}}
    _, run = plan(env={"VMM_MODE": "slow", "VMM_MAX_SLOTS": "8"}, prices=(C, V), state=st)
    assert "S29.TO" in sells(run({"S29.TO": 10}, 0))


def test_slow_mode_no_buys_between_reviews_without_deposit(plan):
    month = make_prices()[0].index[-1].strftime("%Y-%m")
    _, run = plan(env={"VMM_MODE": "slow", "VMM_MAX_SLOTS": "8"}, state={"last_review_month": month})
    assert not buys(run({}, 100))
    assert buys(run({}, 2000))  # a deposit day still buys


def test_slow_mode_max_8_stocks(plan):
    _, run = plan(env={"VMM_MODE": "slow", "VMM_MAX_SLOTS": "8"})
    assert len(buys(run({}, 50_000))) <= 8


def test_market_below_200d_no_buys(plan):
    C, V = make_prices()
    C["XIU.TO"] = C["XIU.TO"].iloc[::-1].values
    _, run = plan(prices=(C, V))
    assert not buys(run({}, 5000))


def test_guard_mode_no_buys(plan):
    _, run = plan(guard=["XIU -3% today"])
    assert not buys(run({}, 5000))


def test_loss_halt_blocks_buys(plan):
    yday = (TODAY - dt.timedelta(days=1)).isoformat()
    _, run = plan(state={"equity_hist": {yday: 10_000}})
    out = run({}, 5000)  # equity 5,000 vs 10,000 high -> 50% down
    assert not buys(out) and any("LOSS HALT" in g for g in out["guard"])


def test_loss_halt_helper(plan):
    p, _ = plan()
    d = TODAY.isoformat()
    assert p.loss_halt({d: 100}, 84, TODAY, 15)[0]
    assert not p.loss_halt({d: 100}, 90, TODAY, 15)[0]
    old = (TODAY - dt.timedelta(days=30)).isoformat()
    assert not p.loss_halt({old: 1000}, 90, TODAY, 15)[0]  # old highs ignored


def test_stale_data_stops_run(plan):
    _, run = plan(prices=make_prices(end=pd.Timestamp(TODAY) - pd.Timedelta(days=14)))
    with pytest.raises(SystemExit, match="STALE"):
        run({}, 1000)


def test_protected_ticker_never_traded(plan):
    _, run = plan(env={"VMM_PROTECTED": "S29.TO,S28.TO"}, prices=make_prices(crash={"S29.TO": 0.5}),
                  state={"ledger": {"S29.TO": 10}})
    out = run({"S29.TO": 10}, 5000)
    assert not ({"S29.TO", "S28.TO"} & ({o["ticker"] for o in out["orders"]}))


def test_state_records_entry_and_equity(plan):
    _, run = plan()
    out = run({}, 2000)
    ns = out["new_state"]
    assert set(ns["entry"]) >= {o["ticker"] for o in buys(out)}
    assert TODAY.isoformat() in ns["equity_hist"]


def test_idle_cash_parked_in_veqt_when_slots_full(plan):
    C, V = make_prices()
    C["VEQT.TO"] = 40.0; V["VEQT.TO"] = 1_000_000
    held = {f"S{i:02d}.TO": 10 for i in range(29, 26, -1)}  # 3 held, slot limit 3 -> nothing free
    _, run = plan(env={"VMM_MAX_SLOTS": "3"}, prices=(C, V), state={"ledger": held})
    out = run(held, 900)
    park = [o for o in buys(out) if o["ticker"] == "VEQT.TO"]
    assert len(park) == 1 and park[0]["units"] * park[0]["limit"] <= 900 - 20
    assert out["idle_cash"] < 150  # per-order cap ($800) leaves a little; next run parks it


def test_momentum_buys_come_before_parking(plan):
    C, V = make_prices()
    C["VEQT.TO"] = 40.0; V["VEQT.TO"] = 1_000_000
    _, run = plan(prices=(C, V))
    out = run({}, 2000)
    assert buys(out)[0]["ticker"] != "VEQT.TO"
    assert sum(o["units"] * o["limit"] for o in buys(out)) <= 2000 + 1


def test_parked_veqt_counts_toward_loss_halt(plan):
    # cash moved into parked VEQT (outside the bot ledger) is not a loss: no false LOSS HALT
    yday = (TODAY - dt.timedelta(days=1)).isoformat()
    C, V = make_prices()
    C["VEQT.TO"] = 40.0; V["VEQT.TO"] = 1_000_000
    _, run = plan(prices=(C, V), state={"equity_hist": {yday: 10_000}})
    units = int(8_000 / C["VEQT.TO"].iloc[-1])
    out = run({"VEQT.TO": units}, 2_000)
    assert not any("LOSS HALT" in g for g in out["guard"])


def test_loss_halt_still_fires_with_veqt(plan):
    yday = (TODAY - dt.timedelta(days=1)).isoformat()
    C, V = make_prices()
    C["VEQT.TO"] = 40.0; V["VEQT.TO"] = 1_000_000
    _, run = plan(prices=(C, V), state={"equity_hist": {yday: 10_000}})
    out = run({"VEQT.TO": int(1_000 / C["VEQT.TO"].iloc[-1])}, 2_000)
    assert any("LOSS HALT" in g for g in out["guard"])

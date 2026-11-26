"""Daily cash-account engine for profit-first development screening."""
import numpy as np
from numba import njit, prange

from daily_engine import HOLDS, RULES_PER_FAMILY

METRICS = ("net_profit", "mtm_drawdown", "tail_loss", "stability", "trades",
           "wins", "losses", "gross_wins", "gross_losses", "capital_loss", "insolvency")


@njit(cache=True)
def simulate(prices, rules, family, variants, start, end, hold, initial, friction, fee, split_factors, dividends, claim, payment, slots):
    cash = initial
    units = 0
    peak = initial
    prior = initial
    midpoint = initial
    worst = 0.
    tail = 0.
    wins = 0
    losses = 0
    gross_wins = 0.
    gross_losses = 0.
    trades = 0
    enter = -1
    leave = -1
    receivable = 0.
    due = np.zeros(slots, np.float64)
    insolvent = 0.
    before = cash
    for day in range(start, end):
        opening, low, close = prices[day]
        if payment[day] >= 0:
            credit = due[payment[day]]
            cash += credit
            receivable -= credit
        if units and split_factors[day] != 1:
            units = int(units * split_factors[day])
        if units and claim[day] >= 0:
            credit = units * dividends[day]
            due[claim[day]] += credit
            receivable += credit
        if day == enter:
            paid = opening * (1 + friction)
            units = max(0, int(np.floor((cash - fee) / paid)))
            if units:
                before = cash + receivable
                cash -= units * paid + fee
                leave = day + hold
        if day == leave:
            cash += units * opening * (1 - friction) - fee
            units = 0
            pnl = cash + receivable - before
            trades += 1
            if pnl > 0:
                wins += 1
                gross_wins += pnl
            elif pnl < 0:
                losses += 1
                gross_losses -= pnl
        # Open marks are known before the low. An intraday high/low order is unavailable.
        peak = max(peak, cash + receivable + units * opening)
        worst = max(worst, (peak - (cash + receivable + units * low)) / peak)
        equity = cash + receivable + units * close
        if equity <= 0:
            insolvent = 1.
        peak = max(peak, equity)
        if prior > 0:
            tail = max(tail, (prior - equity) / prior)
        prior = equity
        if day == start + (end - start) // 2 - 1:
            midpoint = equity
        if not units and day + 1 + hold < end:
            signal = True
            for k in range(len(family)):
                if not rules[family[k], variants[k], day]:
                    signal = False
                    break
            if signal:
                enter = day + 1
    terminal = cash + receivable
    stability = min(midpoint / initial - 1, terminal / midpoint - 1) if midpoint > 0 else -1.
    return (terminal - initial, worst, tail, stability, float(trades), float(wins),
            float(losses), gross_wins, gross_losses, max(0., initial - terminal), insolvent)


@njit(cache=True, parallel=True)
def evaluate(ids, groups, prices, rules, splits, capital, friction, fee, actions):
    depth = groups.shape[1]
    width = RULES_PER_FAMILY ** depth
    output = np.empty((len(ids), 2 * len(METRICS)))
    for i in prange(len(ids)):
        identifier = ids[i]
        hold = HOLDS[identifier % len(HOLDS)]
        encoded = identifier // len(HOLDS)
        family = groups[encoded // width]
        variants = np.empty(depth, dtype=np.int64)
        for k in range(depth):
            variants[k] = encoded % RULES_PER_FAMILY
            encoded //= RULES_PER_FAMILY
        for split in range(2):
            result = simulate(prices, rules, family, variants, splits[split], splits[split + 1],
                              hold, capital, friction, fee, *actions)
            for metric in range(len(METRICS)):
                output[i, split * len(METRICS) + metric] = result[metric]
    return output


def selftest():
    prices = np.array([[10., 10., 10.], [10., 5., 8.], [8., 7., 8.], [15., 14., 15.]])
    rules = np.ones((1, 1, len(prices)), dtype=np.bool_)
    selected = np.array([0], dtype=np.int64)
    neutral = (np.ones(4), np.zeros(4), np.full(4, -1), np.full(4, -1), 0)
    net, risk, tail, _, trades, wins, losses, _, _, capital_loss, _ = simulate(
        prices, rules, selected, selected, 0, 4, 2, 100., 0., 0., *neutral
    )
    assert (net, risk, tail, trades, wins, losses, capital_loss) == (50., .5, .2, 1, 1, 0, 0)
    assert simulate(prices, rules, selected, selected, 0, 3, 2, 100., 0., 0., *neutral)[4] == 0
    charged = simulate(prices, rules, selected, selected, 0, 4, 2, 100., .01, 1., *neutral)
    assert np.isclose(charged[0], 9 * (15 * .99 - 10 * 1.01) - 2)
    split_prices = np.array([[10., 10., 10.], [10., 10., 10.], [5., 5., 5.], [5., 5., 5.]])
    action = (np.array([1., 1., 2., 1.]), np.array([0., 0., .5, 0.]),
              np.array([-1, -1, 0, -1]), np.array([-1, -1, -1, 0]), 1)
    result = simulate(split_prices, rules, selected, selected, 0, 4, 2, 100., 0., 0., *action)
    assert result[0] == 10. and result[1] == 0.
    no_payment = (*action[:3], np.full(4, -1), 1)
    assert simulate(split_prices, rules, selected, selected, 0, 4, 2, 100., 0., 0., *no_payment)[0] == 10.



if __name__ == "__main__":
    selftest()
    print("PASS: mark-to-market lows, tail loss, split limits and execution friction")

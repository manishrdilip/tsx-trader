import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import sys
import datetime as dt
import gzip

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "vmm_bot"))
import plan

def get_data():
    tickers = plan.universe()
    tickers.append("XIU.TO")
    tickers = list(set(tickers))
    
    print(f"Downloading data for {len(tickers)} tickers...")
    # We download from 1998-12-01 to ensure we have 253 days of history by 2000-01-03
    data = yf.download(tickers, start="1998-12-01", auto_adjust=True, progress=False, group_by="ticker", threads=True)
    
    close_frames = {}
    open_frames = {}
    vol_frames = {}
    
    if isinstance(data.columns, pd.MultiIndex):
        for t in tickers:
            if t in data.columns.get_level_values(0):
                close_frames[t] = data[t]["Close"]
                open_frames[t] = data[t]["Open"]
                vol_frames[t] = data[t]["Volume"]
    else:
        # single ticker fallback
        t = tickers[0]
        close_frames[t] = data["Close"]
        open_frames[t] = data["Open"]
        vol_frames[t] = data["Volume"]
        
    C = pd.DataFrame(close_frames)
    O = pd.DataFrame(open_frames)
    V = pd.DataFrame(vol_frames)
    
    return C, O, V

def run_sim():
    C, O, V = get_data()
    
    # Precompute indicators
    r12 = C / C.shift(253) - 1
    sma200 = C.rolling(200).mean()
    dv20 = (C * V).rolling(20).median()
    
    # Mask for days to simulate
    sim_days = C.index[C.index >= "2000-01-03"]
    if len(sim_days) == 0:
        print("No simulation days found.")
        return
        
    cash = 3000.0
    holdings = {} # ticker -> {'shares', 'entry_date', 'max_c', 'entry_price'}
    rebuy_blocks = {} # ticker -> sale_price
    
    trades = []
    daily_records = []
    trade_id = 1
    
    # We need to iterate over simulation days.
    # On day `d`, we execute trades based on signals from `prev_d`.
    # Then we compute new signals on `d` for execution on `next_d`.
    
    # To start on 2000-01-03, we need signals from the prior trading day.
    # Actually, it's easier to loop over signal days, and execute on the next available day.
    
    all_dates = C.index.tolist()
    
    missing_data_tickers = set()

    for i in range(len(all_dates) - 1):
        d = all_dates[i]
        next_d = all_dates[i+1]
        
        if next_d < pd.Timestamp("2000-01-03"):
            continue
            
        c = C.loc[d]
        c_next_open = O.loc[next_d]
        
        # update max_c for current holdings
        for t in holdings:
            if pd.notna(c.get(t)):
                holdings[t]['max_c'] = max(holdings[t]['max_c'], c[t])
                
        is_monthly_review = (d.month != next_d.month)
        
        sells_to_execute = []
        
        # 1. Check sell rules
        for t in list(holdings.keys()):
            if pd.isna(c.get(t)):
                continue # Skip ticker on any day it has no price data
                
            held_days = (d.date() - holdings[t]['entry_date']).days
            
            trail_hit = False
            if c[t] <= holdings[t]['max_c'] * (1 - 0.28):
                trail_hit = True
                
            why = []
            if trail_hit:
                why.append("trail28")
                
            if is_monthly_review and held_days >= 91 and not trail_hit:
                if c[t] < sma200.loc[d, t]:
                    why.append("200d")
                else:
                    # check top 40%
                    elig = (c >= 1) & (c <= 100) & (dv20.loc[d] >= 300_000) & (C.loc[:d, :].notna().sum() >= 253)
                    if "XIU.TO" in elig: elig["XIU.TO"] = False
                    r = r12.loc[d, elig].dropna()
                    if len(r) > 0:
                        top40 = r.quantile(0.6)
                        if pd.notna(r12.loc[d, t]) and r12.loc[d, t] < top40:
                            why.append("top40")
                            
            if why:
                sells_to_execute.append((t, why[0]))
                if trail_hit:
                    rebuy_blocks[t] = c[t] # Wait for 10% drop below sale price
                    
        # Execute sells
        actions_today = []
        for t, reason in sells_to_execute:
            if pd.isna(c_next_open.get(t)):
                missing_data_tickers.add(t)
                continue # Cannot fill if no open price
                
            sell_px = c_next_open[t]
            shares = holdings[t]['shares']
            cash += shares * sell_px
            pnl_cad = (sell_px - holdings[t]['entry_price']) * shares
            pnl_pct = (sell_px / holdings[t]['entry_price'] - 1) * 100
            days_held = (next_d.date() - holdings[t]['entry_date']).days
            
            trades.append({
                'trade_id': trade_id,
                'ticker': t,
                'buy_date': holdings[t]['entry_date'].isoformat(),
                'buy_price': holdings[t]['entry_price'],
                'shares': shares,
                'sell_date': next_d.date().isoformat(),
                'sell_price': sell_px,
                'sell_rule': reason,
                'days_held': days_held,
                'pnl_cad': pnl_cad,
                'pnl_pct': pnl_pct
            })
            trade_id += 1
            actions_today.append(f"SELL {t}")
            del holdings[t]
            
        # 2. Check buy rules (only at monthly review)
        if is_monthly_review:
            # check XIU 200d
            xiu_ok = False
            if pd.notna(c.get("XIU.TO")) and pd.notna(sma200.loc[d, "XIU.TO"]):
                xiu_ok = c["XIU.TO"] > sma200.loc[d, "XIU.TO"]
                
            if xiu_ok:
                elig = (c >= 1) & (c <= 100) & (dv20.loc[d] >= 300_000) & (C.loc[:d, :].notna().sum() >= 253)
                if "XIU.TO" in elig: elig["XIU.TO"] = False
                
                r = r12.loc[d, elig].dropna()
                if len(r) > 0:
                    top10 = r.quantile(0.9)
                    ranked = r[(r >= top10) & (c[r.index] > sma200.loc[d, r.index])].sort_values(ascending=False)
                    
                    # Sizing from plan.py
                    holdings_val = sum(holdings[tk]['shares'] * (c[tk] if pd.notna(c[tk]) else 0) for tk in holdings)
                    equity = cash + holdings_val
                    mom_budget = equity # INDEX_LEG is assumed false
                    
                    if mom_budget >= 2000:
                        slots = int(min(20, max(5, mom_budget // 400.0)))
                        per = mom_budget / slots
                        order_cap = max(800, 0.10 * equity)
                        
                        free_slots = 20 - len(holdings)
                        
                        for t in ranked.index:
                            if free_slots <= 0: break
                            if t in holdings: continue
                            
                            # rebuy block check
                            if t in rebuy_blocks:
                                if c[t] > rebuy_blocks[t] * (1 - 0.10):
                                    continue # Not 10% below sale price yet
                                del rebuy_blocks[t]
                                
                            if pd.isna(c_next_open.get(t)):
                                missing_data_tickers.add(t)
                                continue
                                
                            buy_px = c_next_open[t]
                            lim = c[t] * 1.01 # plan.py buy limit is prev close * 1.01
                            
                            if lim > cash or lim > order_cap:
                                continue
                                
                            u = max(1, int(min(per, cash, order_cap) // buy_px))
                            cost = u * buy_px
                            
                            if cash >= cost:
                                holdings[t] = {
                                    'shares': u,
                                    'entry_date': next_d.date(),
                                    'entry_price': buy_px,
                                    'max_c': buy_px
                                }
                                cash -= cost
                                free_slots -= 1
                                actions_today.append(f"BUY {t}")

        # Compute daily stats on next_d (using next_d's close if available, else open)
        c_today = C.loc[next_d]
        holdings_val = 0
        h_list = []
        for t, v in holdings.items():
            px = c_today[t] if pd.notna(c_today.get(t)) else v['entry_price']
            holdings_val += v['shares'] * px
            h_list.append(f"{t}:{v['shares']}")
            
        equity = cash + holdings_val
        prev_equity = daily_records[-1]['equity'] if daily_records else 3000.0
        
        daily_records.append({
            'date': next_d.date().isoformat(),
            'cash': cash,
            'holdings_value': holdings_val,
            'equity': equity,
            'daily_pnl_cad': equity - prev_equity,
            'number_of_holdings': len(holdings),
            'holdings': "|".join(h_list),
            'actions': "|".join(actions_today)
        })

    # Close open positions at the end of the simulation
    last_date = all_dates[-1]
    c_last = C.loc[last_date]
    for t, v in list(holdings.items()):
        sell_px = c_last[t] if pd.notna(c_last.get(t)) else v['entry_price']
        shares = v['shares']
        pnl_cad = (sell_px - v['entry_price']) * shares
        pnl_pct = (sell_px / v['entry_price'] - 1) * 100
        days_held = (last_date.date() - v['entry_date']).days
        trades.append({
            'trade_id': trade_id,
            'ticker': t,
            'buy_date': v['entry_date'].isoformat(),
            'buy_price': v['entry_price'],
            'shares': shares,
            'sell_date': last_date.date().isoformat(),
            'sell_price': sell_px,
            'sell_rule': 'still_open',
            'days_held': days_held,
            'pnl_cad': pnl_cad,
            'pnl_pct': pnl_pct
        })
        trade_id += 1
        
    trades_df = pd.DataFrame(trades)
    daily_df = pd.DataFrame(daily_records)
    
    # Yearly stats
    if not daily_df.empty:
        daily_df['year'] = pd.to_datetime(daily_df['date']).dt.year
        yearly_records = []
        for year, group in daily_df.groupby('year'):
            start_eq = group['equity'].iloc[0]
            end_eq = group['equity'].iloc[-1]
            ret = (end_eq / start_eq - 1) * 100
            
            # Max DD
            roll_max = group['equity'].cummax()
            dd = (group['equity'] / roll_max - 1) * 100
            max_dd = dd.min()
            
            # trades in year
            trades_in_year = trades_df[trades_df['sell_date'].str.startswith(str(year))] if not trades_df.empty else pd.DataFrame()
            n_trades = len(trades_in_year)
            
            yearly_records.append({
                'year': year,
                'start equity': start_eq,
                'end equity': end_eq,
                'return %': ret,
                'max drawdown %': max_dd,
                'number of trades': n_trades
            })
        yearly_df = pd.DataFrame(yearly_records)
    else:
        yearly_df = pd.DataFrame()
        
    # Save outputs
    out_dir = os.path.join(ROOT, "lab", "gemini_vmm_2000")
    os.makedirs(out_dir, exist_ok=True)
    
    trades_df.to_csv(os.path.join(out_dir, "trades.csv"), index=False)
    
    daily_csv = os.path.join(out_dir, "daily.csv.gz")
    with gzip.open(daily_csv, 'wt') as f:
        daily_df.drop(columns=['year']).to_csv(f, index=False)
        
    yearly_df.to_csv(os.path.join(out_dir, "yearly.csv"), index=False)
    
    print(f"ROWS_WRITTEN_TRADES: {len(trades_df)}")
    print(f"ROWS_WRITTEN_DAILY: {len(daily_df)}")
    print(f"ROWS_WRITTEN_YEARLY: {len(yearly_df)}")
    if not daily_df.empty:
        print(f"DATE_RANGE: {daily_df['date'].iloc[0]} to {daily_df['date'].iloc[-1]}")
    print(f"MISSING_DATA: {list(missing_data_tickers)}")
    print(f"Simulation complete. Trades: {len(trades_df)}")

if __name__ == "__main__":
    run_sim()

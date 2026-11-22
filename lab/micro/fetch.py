"""Download free Yahoo intraday candles: 1m (last ~29 days, 7-day chunks) and 5m (last 60 days)."""
import datetime as dt, os, time, pandas as pd, yfinance as yf
TSX = "RY TD BNS BMO CM NA ENB TRP CNQ SU CVE IMO TOU CP CNR SHOP CSU BN BAM MFC SLF GWO POW ABX AEM FNV WPM K NTR TECK-B CCO FM ATD L DOL QSR WCN BCE T RCI-B FTS EMA H OTEX GIB-A WSP CAE TRI IFC CTC-A MG".split()
NSE = "RELIANCE TCS HDFCBANK ICICIBANK INFY BHARTIARTL ITC SBIN LT HINDUNILVR KOTAKBANK AXISBANK BAJFINANCE MARUTI SUNPHARMA HCLTECH TITAN ULTRACEMCO M&M NTPC ONGC POWERGRID TATAMOTORS TATASTEEL ADANIENT ADANIPORTS JSWSTEEL COALINDIA NESTLEIND WIPRO ASIANPAINT BAJAJFINSV TECHM GRASIM HINDALCO CIPLA DRREDDY EICHERMOT HEROMOTOCO BRITANNIA APOLLOHOSP TATACONSUM INDUSINDBK SBILIFE HDFCLIFE BPCL SHRIRAMFIN TRENT BEL".split()
syms = [s + ".TO" for s in TSX] + [s + ".NS" for s in NSE]
os.makedirs("data", exist_ok=True)
end = dt.datetime.utcnow()
for iv, days, chunk in [("1m", 29, 7), ("5m", 59, 59)]:
    out = []
    for s in syms:
        parts, t1 = [], end
        while (end - t1).days < days:
            t0 = max(t1 - dt.timedelta(days=chunk), end - dt.timedelta(days=days))
            try:
                df = yf.download(s, start=t0, end=t1, interval=iv, progress=False, auto_adjust=False, multi_level_index=False)
            except Exception as e:
                print(s, iv, e); df = pd.DataFrame()
            if len(df): parts.append(df)
            t1 = t0; time.sleep(0.3)
        if parts:
            df = pd.concat(parts).sort_index(); df = df[~df.index.duplicated()]
            df["sym"] = s; out.append(df[["Open", "High", "Low", "Close", "Volume", "sym"]])
        print(iv, s, sum(len(p) for p in parts))
    pd.concat(out).to_parquet(f"data/bars_{iv}.parquet")

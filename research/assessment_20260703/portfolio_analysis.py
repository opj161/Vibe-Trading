import numpy as np, pandas as pd
R = "/home/j_opp/projects/Vibe-Trading"

def load_eq(path, col="equity"):
    df = pd.read_csv(path)
    tcol = "timestamp" if "timestamp" in df.columns else df.columns[0]
    df[tcol] = pd.to_datetime(df[tcol], utc=True).dt.tz_localize(None).dt.floor("D")
    return df.set_index(tcol)[col]

def stats(r, label, bpy=365):
    r = r.dropna()
    eq = (1 + r).cumprod()
    yrs = len(r) / bpy
    ann = eq.iloc[-1] ** (1 / yrs) - 1
    sh = r.mean() / r.std() * np.sqrt(bpy) if r.std() > 0 else np.nan
    dd = ((eq - eq.cummax()) / eq.cummax()).min()
    print(f"{label:34s} ann={ann*100:+7.1f}%  sharpe={sh:5.2f}  maxDD={dd*100:6.1f}%  n={len(r)}")
    return ann, sh, dd

# --- champion spliced: ext train to 2025-06-30, fwd from 2025-07-01 ---
za4_tr = load_eq(f"{R}/agent/runs/v_ZA4_regimeconviction_ext_train/artifacts/equity.csv")
za4_fw = load_eq(f"{R}/agent/runs/fwd_ZA4_20260702/artifacts/equity.csv")
r_tr = za4_tr.pct_change().dropna(); r_fw = za4_fw.pct_change().dropna()
r_za4 = pd.concat([r_tr[r_tr.index <= "2025-06-30"], r_fw[r_fw.index >= "2025-07-01"]])
r_za4 = r_za4[~r_za4.index.duplicated()]

# calendar-daily reindex (strategy flat days = 0)
cal = pd.date_range(r_za4.index.min(), r_za4.index.max(), freq="D")
r_za4d = r_za4.reindex(cal, fill_value=0.0)

# --- BTC benchmark from the option tape's own index series ---
idx = pd.read_csv(f"{R}/research/vrp_deribit/derived/daily_index.csv", parse_dates=["date"])
btc = idx.set_index(idx["date"].dt.tz_localize(None))["index_close"]
r_btc = btc.pct_change().reindex(cal).fillna(0.0)
# BTC 200dma timing, 0.1% per flip
sig = (btc > btc.rolling(200).mean()).astype(float).reindex(cal).ffill().fillna(0.0)
flips = sig.diff().abs().fillna(0.0)
r_dma = (sig.shift(1).fillna(0.0) * r_btc - flips * 0.001)

print("=== A. Benchmark honesty, common window", cal[0].date(), "->", cal[-1].date(), "===")
stats(r_za4d, "ZA4 champion (train+fwd spliced)")
stats(r_btc, "BTC buy & hold")
stats(r_dma, "BTC 200dma timing (0.1%/flip)")

print("\n=== B. Forward year only (2025-07-01 ->) — the only virgin evidence ===")
fw_mask = cal >= "2025-07-01"
stats(r_za4d[fw_mask], "ZA4 forward")
stats(r_btc[fw_mask], "BTC B&H forward")
stats(r_dma[fw_mask], "BTC 200dma forward")

# --- M1 macro + VRP sleeves ---
m1 = load_eq(f"{R}/agent/runs/v_M1_macro_aqrblend_full_adjfix/artifacts/equity.csv")
r_m1 = m1.pct_change().reindex(cal, fill_value=0.0)
print("\n=== C. Sleeve stats on common window ===")
stats(r_m1, "M1 macro (SPY+GLD blend)")
vrps = {}
for name in ["HEDGED-UNCOND", "HEDGED-COND", "UNHEDGED-UNCOND", "UNHEDGED-COND"]:
    v = load_eq(f"{R}/research/vrp_deribit/derived/phase3_equity_{name}.csv")
    rv = v.pct_change().reindex(cal, fill_value=0.0)
    vrps[name] = rv
    stats(rv, f"VRP {name}")

print("\n=== D. Correlations (daily, common window) ===")
best_vrp = vrps["HEDGED-COND"]
df = pd.DataFrame({"ZA4": r_za4d, "M1": r_m1, "VRP_hc": best_vrp, "BTC": r_btc})
print(df.corr().round(3).to_string())

print("\n=== E. Portfolio blends (daily-rebalanced weights, gross) ===")
stats(0.30*df.ZA4 + 0.70*df.M1, "CP3-like 30/70 crypto/macro")
stats(0.30*df.ZA4 + 0.55*df.M1 + 0.15*best_vrp, "30/55/15 + VRP sleeve")
stats(0.30*df.ZA4 + 0.50*df.M1 + 0.20*vrps["HEDGED-UNCOND"], "30/50/20 + VRP uncond")

print("\n=== F. Kelly / leverage (ZA4 spliced daily) ===")
mu, var = r_za4d.mean(), r_za4d.var()
kelly = mu / var
print(f"daily mu={mu:.5f} sigma={r_za4d.std():.5f}  full-Kelly leverage={kelly:.2f}x  half-Kelly={kelly/2:.2f}x")
rng = np.random.default_rng(7)
for lev in [1.0, 1.5, 2.0, 2.5, 3.0]:
    dds = []
    for _ in range(400):
        sim = rng.choice(r_za4d.values, size=len(r_za4d), replace=True) * lev
        e = np.cumprod(1 + sim)
        dds.append(((e - np.maximum.accumulate(e)) / np.maximum.accumulate(e)).min())
    dds = np.array(dds)
    print(f"lev={lev:.1f}x  bootstrap P(maxDD<-40%)={ (dds<-0.40).mean()*100:5.1f}%   median maxDD={np.median(dds)*100:6.1f}%")

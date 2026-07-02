import numpy as np, pandas as pd, sys
R = "/home/j_opp/projects/Vibe-Trading"
sys.path.insert(0, f"{R}/agent")
from backtest.validation import deflated_sharpe_ratio

def load_eq(path, col="equity"):
    df = pd.read_csv(path)
    t = "timestamp" if "timestamp" in df.columns else df.columns[0]
    df[t] = pd.to_datetime(df[t], utc=True).dt.tz_localize(None).dt.floor("D")
    return df.set_index(t)[col]

def stats(r, label, bpy=365):
    r = r.dropna(); eq = (1+r).cumprod(); yrs = len(r)/bpy
    ann = eq.iloc[-1]**(1/yrs)-1; sh = r.mean()/r.std()*np.sqrt(bpy)
    dd = ((eq-eq.cummax())/eq.cummax()).min()
    print(f"{label:36s} ann={ann*100:+7.1f}%  sharpe={sh:5.2f}  maxDD={dd*100:6.1f}%")

za4f = load_eq(f"{R}/agent/runs/fwd_ZA4_20260702/artifacts/equity.csv").pct_change().dropna()
za4f = za4f[za4f.index >= "2025-07-01"]
cal = pd.date_range("2025-07-01", "2026-06-30", freq="D")
za4f = za4f.reindex(cal, fill_value=0.0)
m1 = load_eq(f"{R}/agent/runs/v_M1_macro_aqrblend_full_adjfix/artifacts/equity.csv").pct_change().reindex(cal, fill_value=0.0)
vrp = load_eq(f"{R}/research/vrp_deribit/derived/phase3_equity_HEDGED-COND.csv").pct_change().reindex(cal, fill_value=0.0)

print("=== Forward year only (virgin evidence, 2025-07 -> 2026-06) ===")
stats(za4f, "ZA4 crypto sleeve")
stats(m1, "M1 macro sleeve")
stats(vrp, "VRP hedged-cond sleeve")
stats(0.30*za4f + 0.70*m1, "30/70 composite")
stats(0.30*za4f + 0.55*m1 + 0.15*vrp, "30/55/15 composite")
print("corr fwd year: ZA4-M1 = %.3f" % za4f.corr(m1))

# Honest deflation: champion train Sharpe deflated by the arc's full design-trial count
za4t = load_eq(f"{R}/agent/runs/v_ZA4_regimeconviction_ext_train/artifacts/equity.csv").pct_change().dropna()
print("\n=== DSR of champion train window under honest trial counts ===")
for n in [10, 50, 100, 200]:
    d = deflated_sharpe_ratio(za4t.values, n_trials=n, bars_per_year=365)
    print(f"n_trials={n:4d}: DSR={d['dsr']*100:6.2f}%  (train SR={d.get('sharpe', float('nan')):.3f})" if 'sharpe' in d else f"n_trials={n:4d}: DSR={d['dsr']*100:6.2f}%")

"""Deployable-configuration menu at retail scale: blends x leverage,
full-window + forward-year stats + bootstrap drawdown risk."""
import numpy as np, pandas as pd
R = "/home/j_opp/projects/Vibe-Trading"

def load_eq(path, col="equity"):
    df = pd.read_csv(path)
    t = "timestamp" if "timestamp" in df.columns else df.columns[0]
    df[t] = pd.to_datetime(df[t], utc=True).dt.tz_localize(None).dt.floor("D")
    return df.set_index(t)[col]

za4_tr = load_eq(f"{R}/agent/runs/v_ZA4_regimeconviction_ext_train/artifacts/equity.csv").pct_change().dropna()
za4_fw = load_eq(f"{R}/agent/runs/fwd_ZA4_20260702/artifacts/equity.csv").pct_change().dropna()
r_za4 = pd.concat([za4_tr[za4_tr.index <= "2025-06-30"], za4_fw[za4_fw.index >= "2025-07-01"]])
cal = pd.date_range(r_za4.index.min(), r_za4.index.max(), freq="D")
r_za4 = r_za4.reindex(cal, fill_value=0.0)
r_m1 = load_eq(f"{R}/agent/runs/v_M1_macro_aqrblend_full_adjfix/artifacts/equity.csv").pct_change().reindex(cal, fill_value=0.0)
fw = cal >= "2025-07-01"

def stats(r, bpy=365):
    eq = (1+r).cumprod(); yrs = len(r)/bpy
    ann = eq.iloc[-1]**(1/yrs)-1; sh = r.mean()/r.std()*np.sqrt(bpy)
    dd = ((eq-eq.cummax())/eq.cummax()).min()
    return ann, sh, dd

def boot_dd(r, lev, n=400, seed=7):
    rng = np.random.default_rng(seed)
    dds = []
    for _ in range(n):
        sim = rng.choice(r.values, size=len(r), replace=True) * lev
        sim = np.maximum(sim, -0.99)
        e = np.cumprod(1+sim)
        dds.append(((e-np.maximum.accumulate(e))/np.maximum.accumulate(e)).min())
    dds = np.array(dds)
    return np.median(dds), (dds < -0.30).mean()

print(f"{'config':>26} | {'full ann':>8} {'sh':>5} {'maxDD':>6} | {'fwd ann':>8} {'sh':>5} {'maxDD':>6} | {'boot medDD':>10} {'P(DD<-30%)':>10}")
for label, w_c, w_m, lev in [
    ("30/70 composite 1x", .30, .70, 1.0),
    ("30/70 composite 1.5x", .30, .70, 1.5),
    ("30/70 composite 2x", .30, .70, 2.0),
    ("50/50 composite 1x", .50, .50, 1.0),
    ("50/50 composite 1.5x", .50, .50, 1.5),
    ("70/30 composite 1x", .70, .30, 1.0),
    ("crypto sleeve only 1x", 1.0, 0.0, 1.0),
]:
    r = (w_c*r_za4 + w_m*r_m1) * lev
    a, s, d = stats(r); af, sf, df_ = stats(r[fw])
    mdd, p30 = boot_dd(w_c*r_za4 + w_m*r_m1, lev)
    print(f"{label:>26} | {a*100:+7.1f}% {s:5.2f} {d*100:5.0f}% | {af*100:+7.1f}% {sf:5.2f} {df_*100:5.0f}% | {mdd*100:9.0f}% {p30*100:9.0f}%")
print("\n(leverage modeled as daily-reset multiple, gross of margin/borrow costs ~1-3%/yr;")
print(" bootstrap: 400 resamples of full common window, per-path max drawdown)")

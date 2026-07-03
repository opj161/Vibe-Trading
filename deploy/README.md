# CPD-1 deployment to the Ubuntu-VM

The daily cycle runs on the always-on **Ubuntu-VM** (`~/.ssh/config` host
`Ubuntu-VM` → 192.168.1.142, user `opj`), repo at
`/home/opj/projects/Vibe-Trading`. Rationale: the dev machine is WSL2, whose
cron dies whenever the Windows host sleeps — and the go-live gate
(`deployment/GO_LIVE_CHECKLIST.md` Phase 3) demands **zero missed daily runs
in the final two weeks** of paper mode.

## Topology

```
WSL2 dev machine                     Ubuntu-VM (always on)
  code + git (source of truth)        code mirror (rsync target)
  research / backtests                .venv (deploy/requirements-vm.txt)
                                      cron: daily cycle / snapshot / weekly report
                                      deployment/state/   <- SYSTEM OF RECORD
                                      research/deribit_snapshot/data/
        <------ deploy/pull_state.sh (state back for inspection + git commit)
        ------> deploy/deploy_to_vm.sh (code out; VM state never touched)
```

- **Code flows dev → VM** (`deploy_to_vm.sh`, rsync, excludes all VM-local
  state so a redeploy can never clobber the ledger).
- **State flows VM → dev** (`pull_state.sh`, additive-only) — pull weekly,
  commit the append-only CSVs (`live_ledger.csv`, `equity_snapshots.csv`,
  `equity_marks.csv`) to git per the repo's ledger discipline.
- **Never run `daily_cycle` in paper mode on the dev machine while the VM
  cycle is live** — it would fork the ledger.

## One-time setup

```bash
./deploy/deploy_to_vm.sh --with-env          # code + .env (Telegram keys)
ssh Ubuntu-VM 'bash /home/opj/projects/Vibe-Trading/deploy/bootstrap_vm.sh'
# seed the paper equity (choose the real intended capital split, 30/70):
ssh Ubuntu-VM "cd /home/opj/projects/Vibe-Trading && .venv/bin/python -c \"
from deployment.ledger import append_equity_snapshot
append_equity_snapshot(date='<START>', venue='binance_spot',  symbol_or_cash='cash', balance_usd=<CRYPTO>)
append_equity_snapshot(date='<START>', venue='ibkr_ucits',    symbol_or_cash='cash', balance_usd=<MACRO>)\""
# validation run (real data, real Telegram):
ssh Ubuntu-VM 'cd /home/opj/projects/Vibe-Trading && .venv/bin/python -m deployment.daily_cycle --auto-paper'
# then schedule:
ssh Ubuntu-VM 'bash /home/opj/projects/Vibe-Trading/deploy/install_cron.sh'
```

## Cron schedule (UTC, pinned via CRON_TZ)

| Time (UTC) | Job | Why this time |
|---|---|---|
| 16:10 daily | `run_daily.sh` → `deployment.daily_cycle --auto-paper` | just after the OKX 16:00 UTC daily bar close the frozen ZA4 config keys on — earlier means a one-bar-stale crypto signal |
| 16:40 daily | `run_snapshot.sh` → Deribit chain snapshotter | any time works; kept near the cycle for one log window |
| 17:00 Mon | `run_weekly_report.sh` → tracking report | weekly QC per CPD-1 §A3 |

Logs land in `deploy/logs/` on the VM (pulled back by `pull_state.sh`).
Telegram carries the same signal: a data-integrity failure, funding REVIEW,
risk tripwire, or the plain daily summary all push to the bot, so a silent
day in Telegram = investigate the cron itself.

## Redeploying after code changes

```bash
./deploy/deploy_to_vm.sh     # state-safe; then optionally re-run bootstrap if deps changed
```

## Notes

- The VM venv installs `deploy/requirements-vm.txt` (curated engine+deployment
  subset), not the full research pyproject — loaders for markets the VM never
  touches degrade gracefully inside the registry's per-module try/except.
- `nautilus_trader` is deliberately NOT on the VM; the HL-testnet drill and
  options research stay on the dev machine (`pip install -e .[nautilus]`).
- Going live later does not change this topology: `daily_cycle --mode live`
  produces tickets + alerts, the human places orders and confirms them
  (`python -m deployment.confirm`, run on the VM so the ledger stays single).

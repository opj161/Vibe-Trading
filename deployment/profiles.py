"""Deployment profiles: which frozen strategies are deployed, which sleeve
each one belongs to, and each strategy's weight of total account equity.

Why this exists (hardening sprint 2026-07-03, reassessment §3.3/§6): the
sleeve mapping used to be a hardcoded ``STRATEGY_SLEEVE`` dict inside
``order_tickets.py`` and the 30/70 split existed only in how the human funded
the venues -- no single place stated "what is deployed", the tracking report
could not weight strategies correctly, and comparing a crypto-only (CTD)
profile against the composite during paper mode had no representation at all.

The DEPLOYED profile is a governance decision recorded in the research log
(findings §85), not a tunable -- change it only with the same discipline as a
strategy freeze. ``CPD_PROFILE`` env var exists for paper-mode side-by-side
comparison runs, never for silently switching the live book.
"""

from __future__ import annotations

import dataclasses
import os

CRYPTO = "crypto"
MACRO = "macro"
VALID_SLEEVES = (CRYPTO, MACRO)


@dataclasses.dataclass(frozen=True)
class Allocation:
    """One deployed strategy's sleeve membership and share of account equity."""

    sleeve: str
    weight: float


@dataclasses.dataclass(frozen=True)
class Profile:
    """A complete deployment configuration.

    Attributes:
        name: Profile identifier (stable, used in reports/alerts).
        allocations: strategy name -> Allocation. Only these strategies
            generate tickets.
        shadow_strategies: run daily for signal state + paper-curve accrual
            (forward arbitration evidence), but never generate tickets.
    """

    name: str
    allocations: dict[str, Allocation]
    shadow_strategies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for strategy, alloc in self.allocations.items():
            if alloc.sleeve not in VALID_SLEEVES:
                raise ValueError(f"{self.name}: {strategy} has unknown sleeve {alloc.sleeve!r}")
            if not 0.0 < alloc.weight <= 1.0:
                raise ValueError(f"{self.name}: {strategy} weight {alloc.weight} outside (0, 1]")
        total = sum(a.weight for a in self.allocations.values())
        if total > 1.0 + 1e-9:
            raise ValueError(f"{self.name}: allocation weights sum to {total} > 1.0")
        overlap = set(self.allocations) & set(self.shadow_strategies)
        if overlap:
            raise ValueError(f"{self.name}: {sorted(overlap)} both deployed and shadow")

    @property
    def strategy_sleeve(self) -> dict[str, str]:
        """strategy -> sleeve, for callers that only need the mapping."""
        return {s: a.sleeve for s, a in self.allocations.items()}

    def sleeve_weight(self, sleeve: str) -> float:
        """Total target share of account equity for one sleeve."""
        return sum(a.weight for a in self.allocations.values() if a.sleeve == sleeve)

    @property
    def all_strategies(self) -> tuple[str, ...]:
        """Deployed + shadow, the full daily signal-run list."""
        return tuple(self.allocations) + self.shadow_strategies


PROFILES: dict[str, Profile] = {
    # CPD-1 as originally frozen: full long/short M1 macro sleeve. Kept for
    # comparison; its macro shorts surface as REVIEW tickets (undecided
    # expression) -- superseded as the deployed profile by cpd1_lf.
    "cpd1": Profile(
        name="cpd1",
        allocations={
            "ZA4": Allocation(CRYPTO, 0.30),
            "M1": Allocation(MACRO, 0.70),
        },
        shadow_strategies=("ZD2",),
    ),
    # THE DEPLOYED PROFILE (governance decision, findings §85): macro sleeve
    # expressed long/flat via the frozen M1LF engine -- engine evidence is
    # one-sided (§84.3: full-window Sharpe 0.92 vs 0.61, maxDD -15.0% vs
    # -19.6%, forward-year 1.43 vs 1.16; M1's short legs lost $486k
    # 2005->2026) and it is what skipping short tickets does anyway, made
    # first-class so the paper reference curve matches what actually trades.
    "cpd1_lf": Profile(
        name="cpd1_lf",
        allocations={
            "ZA4": Allocation(CRYPTO, 0.30),
            "M1LF": Allocation(MACRO, 0.70),
        },
        shadow_strategies=("ZD2",),
    ),
    # Crypto-only profiles (external-assessment CTD lane): for paper-mode
    # comparison only unless a future governance decision promotes one.
    "ctd_za4": Profile(
        name="ctd_za4",
        allocations={"ZA4": Allocation(CRYPTO, 1.0)},
        shadow_strategies=("ZD2",),
    ),
    "ctd_zd2": Profile(
        name="ctd_zd2",
        allocations={"ZD2": Allocation(CRYPTO, 1.0)},
    ),
}

DEPLOYED_PROFILE_NAME = "cpd1_lf"


def active_profile() -> Profile:
    """The profile the daily cycle runs. ``CPD_PROFILE`` env var overrides for
    side-by-side paper comparisons; unknown names fail loudly (never fall back
    silently -- a typo must not quietly deploy the wrong book)."""
    name = os.environ.get("CPD_PROFILE", DEPLOYED_PROFILE_NAME)
    if name not in PROFILES:
        raise ValueError(f"Unknown deployment profile {name!r} (have {sorted(PROFILES)})")
    return PROFILES[name]

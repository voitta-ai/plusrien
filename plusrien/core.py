"""Core schema and merge for plusrien.

A production-coverage fact table: which symbols actually executed, in which
environment, how many observations backed that conclusion, and what a zero
licenses you to claim.

The invariant this library owns is NOT collection. Collection differs wildly
per platform (JaCoCo exec files, sys.monitoring, CloudWatch dimensions). What
is common is the symbol identity scheme, the merge, and the statistics of
zero. Collectors are plugs that emit Observation; consumers read the fold.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True)
class Observation:
    """One partial observation of a symbol's execution over a window.

    symbol_id is a language-tagged, stable identity. One namespace has to hold
    a Java method, a Python function, and an HTTP route, or a metrics-derived
    collector cannot feed the same table as a bytecode-derived one:

        http:POST /api/v1/evaluate
        java:com.example.Service#method(ArgType,OtherType)
        py:module.path#function/3

    Fully-qualified names are used rather than file and line because line
    numbers shift on every commit, which makes accumulation across releases
    meaningless. Methods and routes survive.

    observations is the denominator, and it must be the hit count of the
    ENCLOSING SCOPE named by scope_id -- not global traffic. This is the single
    easiest way to ship a confident false-dead. If a function never ran for
    anyone in the window, "the branch inside it never fired" carries exactly
    zero information, yet against a global denominator it renders as a hard
    zero with a tight bound. The ratio hits/observations is the evidence; the
    raw count is noise.

    scope_id names that enclosing scope: the controller for a route, the
    function for a branch, the component for a UI path. Empty means
    service-level scope, which is only defensible when siblings under the same
    scope are demonstrably live and therefore prove the instrument works.

    unit says what observations counts, and collectors disagree about this in a
    way that changes how a bound must be read:

      "executions" -- a counting collector (metrics, access logs). The
          denominator is individual invocations, so a bound is per-invocation
          and can be extremely tight on a high-traffic service.
      "windows" -- a BINARY collector (JaCoCo, class-load liveness, beacons).
          These report only "executed at least once in this dump", never how
          many times. A single dump therefore supports no rate bound at all.
          Accumulate N dumps in which the enclosing scope was live and the
          denominator becomes N observation windows, which restores a bound at
          window granularity: much weaker than per-invocation, but honest and
          stateable.

    Mixing units under one symbol makes the bound meaningless, so merge keys on
    unit and the report prints it beside every bound.
    """

    symbol_id: str
    env: str
    source: str
    window_start: datetime
    window_end: datetime
    observations: int
    hits: int
    scope_id: str = ""
    unit: str = "executions"
    synthetic: bool = False


def merge(records: Iterable[Observation]) -> list[Observation]:
    """Fold partial observations into one row per (symbol_id, env, scope_id, unit).

    Associative and commutative, so merge order never matters and partial
    observations may arrive forever, from any fleet, in any language. The
    store is therefore an append-only set of snapshots and the answer is a
    reduction over them. No database, no coordination, no mutation.

    Synthetic observations are dropped, not summed. Canaries, health checks
    and load tests light up paths that real users never reach, and a map that
    counts them launders dead code as live.

    plusrien: denominators are summed across records, which is correct only
    when each record covers a disjoint window. Overlapping collection runs
    double-count and inflate the confidence bound. Deduplicate by window
    upstream if a collector can emit overlapping runs.
    """
    acc: dict[tuple[str, str, str, str], Observation] = {}
    for rec in records:
        if rec.synthetic:
            continue
        key = (rec.symbol_id, rec.env, rec.scope_id, rec.unit)
        prev = acc.get(key)
        if prev is None:
            acc[key] = rec
            continue
        acc[key] = replace(
            prev,
            source=prev.source if prev.source == rec.source else "merged",
            window_start=min(prev.window_start, rec.window_start),
            window_end=max(prev.window_end, rec.window_end),
            observations=prev.observations + rec.observations,
            hits=prev.hits + rec.hits,
        )
    retval = sorted(acc.values(), key=lambda r: (r.hits, r.symbol_id))
    return retval


def zero_hit_upper_bound(observations: int) -> float:
    """Ninety-five percent upper bound on a symbol's true rate given zero hits.

    The rule of three: observing zero events in n independent trials places the
    95% upper confidence bound on the event rate at 3/n. This is the whole
    answer to "absence of evidence is not evidence of absence" -- it converts
    "we saw nothing" into a number someone can argue with, and it prices
    sampling honestly. Three percent of a high-traffic service is still
    billions of observations and a very tight bound; three percent of a quiet
    service is worthless, and this says so out loud.
    """
    if observations <= 0:
        retval = 1.0
    else:
        retval = 3.0 / observations
    return retval


def silent(rows: Iterable[Observation], min_observations: int = 0) -> list[Observation]:
    """Symbols with zero hits, optionally gated on a minimum denominator.

    A candidate, not a verdict. Recovery paths, annual branches and fire
    escapes show zero too. What this buys is that the conversation now starts
    from evidence rather than from memory.
    """
    retval = [
        r for r in rows if r.hits == 0 and r.observations >= min_observations
    ]
    return retval

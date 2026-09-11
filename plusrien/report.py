"""Render a merged fact table as a human- and agent-readable report."""

from .core import Observation, silent, zero_hit_upper_bound


def render(rows: list[Observation]) -> str:
    if not rows:
        retval = "no observations"
        return retval

    window_start = min(r.window_start for r in rows)
    window_end = max(r.window_end for r in rows)
    days = max((window_end - window_start).days, 0)
    denominator = max(r.observations for r in rows)
    scope = rows[0].scope_id or "(service)"

    lines = []
    lines.append(f"window      {window_start.date()} .. {window_end.date()}  ({days}d)")
    lines.append(f"scope       {scope}")
    lines.append(f"observed    {denominator:,}  (enclosing-scope denominator)")
    lines.append("")
    lines.append("ran:")
    for row in sorted(rows, key=lambda r: -r.hits):
        if row.hits > 0:
            lines.append(f"  {row.hits:>18,}  {row.symbol_id}")

    quiet = silent(rows)
    if quiet:
        lines.append("")
        lines.append("never ran:")
        for row in quiet:
            bound = zero_hit_upper_bound(row.observations)
            lines.append(f"  {0:>18}  {row.symbol_id}")
            lines.append(f"  {'':>18}  95% upper bound on true rate: {bound:.2e}")

    lines.append("")
    lines.append(
        "A zero is a candidate, not a verdict. Recovery paths, annual branches"
    )
    lines.append(
        "and fire escapes also show zero. The bound says how hard the zero is."
    )
    retval = "\n".join(lines)
    return retval

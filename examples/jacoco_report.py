"""Report on a JaCoCo XML file. Works against any Java project.

    PYTHONPATH=. python3 examples/jacoco_report.py path/to/jacocoTestReport.xml

Note what the output says about methods whose enclosing class shows zero. Those
rows are inadmissible rather than dead: if the class never executed in this
window, a zero on its methods carries no information. That most commonly means
the execution data predates a bytecode change, which JaCoCo warns about and
then succeeds anyway.
"""

import sys

from plusrien.collectors.jacoco import collect
from plusrien.core import merge, silent, zero_hit_upper_bound


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)

    rows = merge(collect(sys.argv[1], env="ci"))
    admissible = [r for r in rows if r.observations > 0]
    inadmissible = [r for r in rows if r.observations == 0]

    print(f"methods           {len(rows)}")
    print(f"admissible        {len(admissible)}  (enclosing class executed)")
    print(f"inadmissible      {len(inadmissible)}  (enclosing class did not)")
    print()

    quiet = silent(admissible, min_observations=1)
    print(f"never executed, enclosing class live: {len(quiet)}")
    for row in quiet[:20]:
        bound = zero_hit_upper_bound(row.observations)
        print(f"  {row.symbol_id}")
        print(f"      95% upper bound: {bound:.3f} per {row.unit[:-1]}")
    if len(quiet) > 20:
        print(f"  ... and {len(quiet) - 20} more")

    print()
    print("One report is one window. A bound this weak is expected and honest;")
    print("accumulate dumps over a long window to tighten it.")


if __name__ == "__main__":
    main()

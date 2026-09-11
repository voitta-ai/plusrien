"""Collector: JaCoCo XML reports.

Deliberately the second collector built, and chosen to be as unlike the
CloudWatch one as possible: bytecode-derived rather than metrics-derived,
method granularity rather than route, offline file rather than cloud API, and
BINARY rather than counting. If Observation survives both, coverage.py and a
browser beacon will fit without further argument.

Two things this collector proves, which is why it was worth building early:

1. JaCoCo does not count. It reports only that a method executed at least once
   within a single execution-data set, never how many times. So one report
   supports no rate bound whatsoever. The denominator has to become the number
   of accumulated observation windows in which the enclosing class was live,
   which is what unit="windows" means. State the unit or the bound lies.

2. JaCoCo cannot merge across releases. Execution data is keyed by a hash of
   the class bytes, so a dump taken before a deploy will not reconcile with
   class files from after it. Observed live while building this, against a
   real report:

     [ant:jacocoReport] Classes in bundle '<project>' do not match with
     execution data. For report generation the same class files must be used
     as at runtime.
     [ant:jacocoReport] Execution data for class
     com/example/service/SomeFactory does not match.

   The build still reported BUILD SUCCESSFUL. That is the dangerous shape: a
   warning, not an error, so an accumulation pipeline spanning deploys silently
   under-reports coverage and manufactures false-deads. Accumulation across
   releases is precisely the job this library exists to do, and it is the job
   JaCoCo's own merge cannot.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from ..core import Observation

_PRIMITIVES = {
    "B": "byte",
    "C": "char",
    "D": "double",
    "F": "float",
    "I": "int",
    "J": "long",
    "S": "short",
    "Z": "boolean",
    "V": "void",
}


def _decode_args(desc: str) -> str:
    """Render a JVM method descriptor's argument list readably.

    (Lcom/foo/Bar;I[Ljava/lang/String;)V -> Bar,int,String[]

    Simple names only. Fully-qualified argument types make the symbol id
    unreadable, and the enclosing class already disambiguates overloads in
    every case that matters in practice.
    """
    inner = desc[desc.index("(") + 1 : desc.index(")")]
    out, i = [], 0
    while i < len(inner):
        arrays = 0
        while inner[i] == "[":
            arrays += 1
            i += 1
        if inner[i] == "L":
            end = inner.index(";", i)
            name = inner[i + 1 : end].split("/")[-1].replace("$", ".")
            i = end + 1
        else:
            name = _PRIMITIVES.get(inner[i], inner[i])
            i += 1
        out.append(name + "[]" * arrays)
    retval = ",".join(out)
    return retval


def _covered(node) -> int:
    for counter in node.findall("counter"):
        if counter.get("type") == "METHOD":
            retval = int(counter.get("covered", "0"))
            return retval
    retval = 0
    return retval


def collect(
    xml_path: str,
    env: str,
    source: str = "jacoco",
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> list[Observation]:
    """One Observation per method in the report, covered or not.

    Unlike a metrics-derived collector, this needs no seeded inventory: JaCoCo
    enumerates every class it was given, so absences are visible for free.
    That asymmetry is worth remembering when adding collectors -- ask whether
    the source can see what did NOT happen, and if it cannot, seed it.
    """
    now = datetime.now(timezone.utc)
    start = window_start or now
    end = window_end or now

    root = ET.parse(xml_path).getroot()
    records = []
    for package in root.findall("package"):
        for klass in package.findall("class"):
            fqcn = klass.get("name", "").replace("/", ".")
            scope_id = f"java:{fqcn}"
            class_live = 1 if _covered(klass) > 0 else 0
            for method in klass.findall("method"):
                name = method.get("name", "")
                args = _decode_args(method.get("desc", "()V"))
                records.append(
                    Observation(
                        symbol_id=f"{scope_id}#{name}({args})",
                        env=env,
                        source=source,
                        window_start=start,
                        window_end=end,
                        # The enclosing-scope control: this method's zero means
                        # nothing if its own class never executed either.
                        observations=class_live,
                        hits=1 if _covered(method) > 0 else 0,
                        scope_id=scope_id,
                        unit="windows",
                    )
                )
    retval = records
    return retval

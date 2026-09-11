# plusrien

> "Il semble que la perfection soit atteinte non quand il n'y a plus rien a
> ajouter, mais quand il n'y a plus rien a retrancher."
>
> "Perfection is attained not when there is nothing more to add, but when there
> is nothing more to take away."
>
> Antoine de Saint-Exupery, *Terre des hommes* (1939), chapter 3, "L'Outil"
> ("The Tool"). English edition: *Wind, Sand and Stars*.
>
> Sources: [Oxford Reference](https://www.oxfordreference.com/display/10.1093/acref/9780191843730.001.0001/q-oro-ed5-00009075)
> and [Wildmind](https://www.wildmind.org/blogs/quote-of-the-month/it-seems-that-perfection-is-attained-not-when-there-is-nothing-more-to-add-but-when-there-is-nothing-more-to-remove-antoine-de-saint-exupery).
>
> He was writing about airplanes, not philosophy. Early aircraft were cluttered
> with exposed pipes and bulky structures; engineering progress meant stripping
> them to functional essence. The name is pronounced roughly "ploo-ree-EN".

Production coverage, used to find dead code.

## The thesis

Coverage in continuous integration measures the test suite, using code as the
yardstick. Coverage in production measures the code, using real traffic as the
yardstick. Same instrument, opposite subject. The entire tooling ecosystem was
built for one direction and never turned around.

The diff between the two is worth more than either alone:

| | ran in prod | never ran in prod |
|---|---|---|
| **covered in CI** | healthy | **dead code with tests** |
| **not covered in CI** | **untested hot path** | triage: dead, or a fire escape |

The top-right cell is why this matters now. Dead code that has tests is
self-justifying. It looks maintained, it looks intentional, and a coding agent
reading both the code and its passing test is doubly convinced. No static tool
finds it, because the test is a real caller.

## What this library is and is not

It produces **facts**. It does not file tickets, open pull requests, or decide
what to delete. Those are policy, and policy is organization-shaped: whether a
finding becomes a Jira issue, a GitHub issue, or nothing belongs in a skill,
not here. That line keeps the library shippable to anyone.

The invariant it owns is not collection. Collection differs wildly per
platform. What is common is three things:

- **Symbol identity.** One namespace holds a Java method, a Python function,
  and an HTTP route, or a metrics-derived collector cannot feed the same table
  as a bytecode-derived one.
- **The merge.** Associative and commutative, so order never matters and
  partial observations may arrive forever from any fleet in any language. The
  store is an append-only set of snapshots; the answer is a fold.
- **The statistics of zero.** The rule of three: zero events in n trials puts
  the 95% upper bound on the true rate at 3/n. State the bound, or it is a vibe
  with a dashboard.

## The denominator is the hard part

A bare reachability signal is near-useless without a control on the enclosing
scope. If a function never ran for anyone in the window, "the branch inside it
never fired" carries zero information, yet against a global denominator it
renders as a hard zero with a tight bound. The ratio is the evidence; the raw
count is noise.

Get this wrong and the tooling ships confident false-deads. This class of
tooling loses trust permanently after one bad deletion.

## Granularity

Method and route level first, not branch. Branch coverage is where both costs
live: runtime overhead, and identity that does not survive a line-number shift
between releases. Fully-qualified names are stable; line numbers are not.
Branch is tier two, and it earns in on the specific case of a dead conditional
inside a live function.

## Tiers, cheapest first

- **Tier 0, already paid for.** Signals the service already emits. Feature-flag
  evaluation counts, metrics carrying an endpoint dimension, access logs. No
  instrumentation, no deploy, and the history already exists. The rule that
  falls out: dead-code toggles should be flags, not literals.
- **Tier 1, cheap.** Class-load liveness on the JVM via Java Flight Recorder,
  or one-line beacons at candidate sites in a browser bundle. Kills whole-file
  dead code at near-zero overhead.
- **Tier 2, real coverage.** JaCoCo agent on a fraction of the fleet in
  `output=tcpserver` mode, dumped on a schedule and merged over a long window.
- **Tier 3, the point.** The accumulated map as an input a coding agent can
  query per symbol, so it stops treating every line as equally true.

Full statement-level instrumentation in a production browser bundle is a
non-starter, so this is probably not one technique. It is two that share a
schema.

## Status

Two collectors, chosen to be as unlike each other as possible so that the
schema is tested rather than asserted.

- **CloudWatch metrics** with an endpoint or uri dimension. Counting, route
  granularity, cloud API, no instrumentation and no deploy. Must be seeded
  with the declared inventory, because a route that never ran has no metric
  and its absence is otherwise invisible.
- **JaCoCo XML.** Binary, method granularity, offline file. Needs no seeding,
  since it enumerates every class it was given.

What building the second one taught, which is why it came early: binary
collectors support no rate bound from a single report, so the denominator has
to become accumulated observation windows. See `unit` in `core.py` and the unit
section of [METHOD.md](METHOD.md).

## Using it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip3 install boto3

PYTHONPATH=. python3 examples/jacoco_report.py build/reports/jacoco/test/jacocoTestReport.xml
```

Read [METHOD.md](METHOD.md) before drawing a conclusion from a zero. The
measurement is easy; the discipline around a negative result is the difficulty.

## Company-specific wiring

Service names, account layouts, route inventories and ticket conventions do not
belong here. Keep them in a separate private repository that depends on this
one. The line: if it would be true at another company, it goes here; if it
names one of your services or processes, it does not.

## Caveats that must survive contact

- **Zero hits is not dead.** Disaster recovery, error handlers, the annual
  reconciliation branch. The observation window must exceed the business cycle.
- **Synthetic traffic launders dead code.** Canaries, health checks and load
  tests light up paths real users never reach. Excluded at the source, or the
  map is worthless.
- **Absence is invisible unless you seed the inventory.** A metrics-derived
  collector can only report on symbols that ran at least once. It must be
  handed the declared symbol set and emit explicit zeros for the rest.
- **The evidence window is when the metric started existing**, not how far back
  you probed.
- **Code is cheap to revert; data is not.** Deleting a class is one revert away.
  Dropping a column or retiring a topic has no undo. Two lanes, two bars.

## License

MIT. See [LICENSE](LICENSE).

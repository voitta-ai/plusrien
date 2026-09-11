# Method

How to use this without fooling yourself. The measurement is easy; the
discipline around a negative result is the whole difficulty.

## Pre-register, or the result proves nothing

A method that only ever confirms what its author already believed is a method
that cannot be wrong. If you pick a candidate because reading the source
convinced you it was dead, and the data agrees, you have validated the
plumbing and learned nothing about the method.

Before querying, write down:

- the symbol
- your prediction: live or dead
- your confidence
- why

Then measure, and record the outcome next to the prediction whether or not you
were right. Being wrong is the point. A wrong prediction on a question reading
could not answer is the only thing that demonstrates the method does something
reading does not.

## Carry a control that must come back live

Include at least one symbol you would bet heavily is alive. If it reads zero,
the instrument is broken, not the code. Without a control, a systematic
collection failure is indistinguishable from a codebase full of dead code, and
it fails in the direction that gets things deleted.

## The denominator is the finding's foundation

A bare reachability signal is near-useless without a control on the enclosing
scope. If a function never ran for anyone in the window, "the branch inside it
never fired" carries zero information, yet against a global denominator it
renders as a hard zero with a tight bound. The ratio is the evidence; the raw
count is noise.

This is not theoretical. On the first real report this library was pointed at,
the two most heavily tested classes in the target codebase read zero coverage,
because the execution data predated a bytecode change. The scope control
marked those rows inadmissible instead of dead. Without it, the tool's first
output would have been a confident false positive on its most-exercised code.

## State the bound

The rule of three: zero events in n trials puts the 95% upper bound on the true
rate at 3/n. Report it with its unit, because collectors disagree about what
they count:

- **counting** collectors (metrics, access logs) give a per-invocation bound,
  which can be extremely tight on a high-traffic service
- **binary** collectors (JaCoCo, class-load liveness, beacons) report only
  "at least once per dump". One report supports no bound at all. Accumulate N
  windows in which the enclosing scope was live and the bound returns at
  window granularity, much weaker but honest

State the bound, or it is a vibe with a dashboard.

## Bound the window honestly

The evidence window is when the instrument started existing, not how far back
you probed. Probing four hundred days against a metric that is sixty-three days
old and reporting four hundred overstates the claim by a factor of six.

## Absence is invisible unless you seed the inventory

Some collectors can only report on symbols that ran at least once. A route that
was never called has no metric at all, so it vanishes from the report rather
than appearing as a zero. Hand those collectors the declared symbol set and
have them emit explicit zeros for the remainder. Ask of every new collector:
can this source see what did **not** happen? If not, seed it.

## Zero hits is not dead

Disaster recovery paths, error handlers, the annual reconciliation branch. The
observation window must exceed the business cycle. Synthetic traffic cuts the
other way: canaries, health checks and load tests light up paths real users
never reach, and a map that counts them launders dead code as live.

## Two lanes for deletion

Code is cheap to revert. Deleting a class costs one revert, at a known moment,
to one person, with version control pointing straight at the removal. Data is
not. Dropping a column, retiring a topic, expiring a prefix: no undo. Two
lanes, two bars for evidence.

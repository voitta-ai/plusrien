"""Collector: AWS CloudWatch metrics that already carry an endpoint dimension.

The cheapest collector there is. It needs no instrumentation, no agent and no
deploy, because it reads what a service already publishes. It exists first to
prove the schema holds across maximally dissimilar sources: if a metrics
scraper and a bytecode-derived JaCoCo parser both fit Observation, then
coverage.py and GCP will fit too.

IMPORTANT -- the seeding requirement. A metrics-derived collector can only
report on symbols that ran at least once, because a symbol that never ran has
no metric at all. The absence IS the finding, and an absence is invisible
unless you know what should have been there. So this collector must be handed
the full declared symbol inventory (routes parsed from the source) and emits
explicit zero-hit rows for everything in the inventory it did not observe.
Bytecode-derived collectors like JaCoCo do not need this; they enumerate every
class themselves.
"""

from datetime import datetime, timedelta, timezone

import boto3

from ..core import Observation

_SECONDS_PER_DAY = 86400


def _paginate_metrics(client, namespace: str) -> list[dict]:
    metrics: list[dict] = []
    token = None
    while True:
        kwargs = {"Namespace": namespace}
        if token:
            kwargs["NextToken"] = token
        page = client.list_metrics(**kwargs)
        metrics.extend(page.get("Metrics", []))
        token = page.get("NextToken")
        if not token:
            break
    retval = metrics
    return retval


def _sum_metric(client, namespace, metric_name, dimensions, start, end) -> float:
    resp = client.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=dimensions,
        StartTime=start,
        EndTime=end,
        Period=_SECONDS_PER_DAY,
        Statistics=["Sum"],
    )
    points = resp.get("Datapoints", [])
    retval = sum(p["Sum"] for p in points)
    return retval


def _window_from_datapoints(client, namespace, metric_name, dimensions, start, end):
    """Real evidence window, bounded by when the metric started existing.

    Probing back further than the metric's own birth date and reporting the
    probe length as the evidence window is the easiest way to overstate a
    zero. The honest bound is the first datapoint, not the query start.
    """
    resp = client.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=dimensions,
        StartTime=start,
        EndTime=end,
        Period=_SECONDS_PER_DAY,
        Statistics=["Sum"],
    )
    points = sorted(resp.get("Datapoints", []), key=lambda p: p["Timestamp"])
    if not points:
        retval = (None, None)
    else:
        retval = (points[0]["Timestamp"], points[-1]["Timestamp"])
    return retval


def collect(
    namespace: str,
    region: str,
    env: str,
    metric_name: str,
    dimension: str,
    expected: list[str],
    scope_id: str,
    symbol_prefix: str = "http:",
    denominator_fn=None,
    lookback_days: int = 400,
    synthetic: bool = False,
) -> list[Observation]:
    """Emit one Observation per expected symbol, including the silent ones.

    expected is the declared inventory, e.g. routes parsed from the source.
    Anything in it with no metric becomes a zero-hit row rather than vanishing.

    denominator_fn(region, start, end) supplies the enclosing-scope denominator
    and is called with the DISCOVERED evidence window, never the probe window.
    Probing back four hundred days and then reporting the probe length as the
    evidence window is the easiest way to overstate a zero by an order of
    magnitude. Falling back to the sum of sibling hits is weaker but not
    circular at this granularity: siblings under the same controller are the
    enclosing scope.
    """
    client = boto3.client("cloudwatch", region_name=region)
    probe_end = datetime.now(timezone.utc)
    probe_start = probe_end - timedelta(days=lookback_days)

    seen: dict[str, list[dict]] = {}
    for metric in _paginate_metrics(client, namespace):
        if metric.get("MetricName") != metric_name:
            continue
        for dim in metric.get("Dimensions", []):
            if dim["Name"] == dimension:
                seen[dim["Value"]] = metric["Dimensions"]

    win_start, win_end = None, None
    hits: dict[str, int] = {}
    for value, dims in seen.items():
        hits[value] = int(
            _sum_metric(client, namespace, metric_name, dims, probe_start, probe_end)
        )
        first, last = _window_from_datapoints(
            client, namespace, metric_name, dims, probe_start, probe_end
        )
        if first is not None:
            win_start = first if win_start is None else min(win_start, first)
            win_end = last if win_end is None else max(win_end, last)

    if win_start is None:
        retval: list[Observation] = []
        return retval

    if denominator_fn is not None:
        total = denominator_fn(region, win_start, win_end)
    else:
        total = sum(hits.values())

    records = []
    for symbol in expected:
        short = symbol.split()[-1].rstrip("/").split("/")[-1]
        observed = hits.get(short, hits.get(symbol, 0))
        records.append(
            Observation(
                symbol_id=symbol
                if symbol.startswith(symbol_prefix)
                else symbol_prefix + symbol,
                env=env,
                source=f"cloudwatch:{namespace}:{region}",
                window_start=win_start,
                window_end=win_end,
                observations=total,
                hits=observed,
                scope_id=scope_id,
                synthetic=synthetic,
            )
        )
    retval = records
    return retval


def alb_request_count(lb_name_pattern: str, region: str, start, end) -> int:
    """Independent denominator from the load balancer itself.

    Using the summed per-symbol hits as the denominator is circular: it can
    only count traffic the instrument already saw. The load balancer counts
    everything that arrived, so the two disagreeing is itself a signal.
    """
    elb = boto3.client("elbv2", region_name=region)
    cw = boto3.client("cloudwatch", region_name=region)
    arns = [
        lb["LoadBalancerArn"]
        for lb in elb.describe_load_balancers()["LoadBalancers"]
        if lb_name_pattern in lb["LoadBalancerName"]
    ]
    if not arns:
        retval = 0
        return retval
    suffix = arns[0].split(":loadbalancer/")[-1]
    retval = int(
        _sum_metric(
            cw,
            "AWS/ApplicationELB",
            "RequestCount",
            [{"Name": "LoadBalancer", "Value": suffix}],
            start,
            end,
        )
    )
    return retval

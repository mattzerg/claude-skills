# Dashboard Patterns

Use these patterns when defining dashboard specs.

## Pattern 1: Decision first

Every dashboard should answer a concrete question such as:

- are signups turning into activated users?
- did the launch generate qualified traffic?
- which channel or segment is underperforming?
- which operator queue needs attention first?

If the question is unclear, the dashboard is not ready to spec.

## Pattern 2: Metric layers

Prefer this stack:

- north-star metric
- supporting metrics
- guardrail metrics
- diagnostic cuts

This prevents dashboards from becoming random collections of charts.

## Pattern 3: Metric definition fields

For each metric, specify:

- exact name
- formula
- grain
- source events / tables
- dimensions / filters
- freshness target
- owner
- decision threshold

## Pattern 4: Activation and funnel dashboards

For activation reporting, define:

- signup event
- activation event set
- activation window
- branch logic if lifecycle messages depend on the events
- breakdowns by source, cohort, and workspace type

## Pattern 5: Public vs internal views

Public analytics pages should optimize for:

- trust
- honesty about sample size
- stable headline metrics

Internal dashboards can carry:

- segmented cuts
- operational exceptions
- owner queues
- draft or experimental counters

## Pattern 6: Read cadence matters

Daily dashboards need fewer, faster metrics.
Weekly dashboards can tolerate slower joins and more interpretation.
Real-time dashboards should be reserved for queues, outages, and operational monitoring.

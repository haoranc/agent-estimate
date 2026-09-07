# Migrating to v0.8

These changes ship in v0.8.0. Update configuration and JSON consumers before
upgrading from v0.7.5.
The [forecast contract and runnable example](../README.md#v08-forecast-contract)
describe the new request format separately.

## R1: remove `settings.review_overhead`

v0.7.5 warned about this ignored configuration key. v0.8 rejects its presence
before model validation and exits with code 2, including when its value is `0`
or `null`. Delete the key from the fleet configuration:

```yaml
# Before
settings:
  friction_multiplier: 1.15
  review_overhead: 15
```

```yaml
# After
settings:
  friction_multiplier: 1.15
```

Select additive review with `--review-mode none`, `standard`, `complex`, or
`3-round` on ordinary CLI estimates. In a `--spec` request, set
`execution_profile.review` instead; `--review-mode` cannot be combined with
`--spec`. For example, one standard round adds 15 minutes:

```yaml
# Under execution_profile in a complete --spec request
review:
  mode: single_round
  expected_rounds: 1
  intensity: standard
```

This removes only the configuration key. The report field
`review_overhead_minutes` and additive review modeling remain available.

## R2: replace the JSON `estimated_cost` alias

v0.7.5 emitted both `estimated_cost` and `heuristic_cost` on each JSON
`agent_load` row. v0.8 emits only `heuristic_cost`. Update consumers, including
those reading the Action's JSON `report` output:

```text
Before: report["agent_load"][0]["estimated_cost"]
After:  report["agent_load"][0]["heuristic_cost"]
```

The value still uses the five-minute-turn cost approximation. It is not a
token-metered charge, and this removal does not introduce a token pricing model.

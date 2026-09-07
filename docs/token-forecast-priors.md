# Caller-supplied token priors

Token forecasts are **not calibrated**. The default typed forecast has
`tokens.basis: unavailable` and two null slots: `expected_tokens_total` and
`expected_tokens_output`. Total means processed tokens, including cache carry;
output is reported separately and is included in total. Neither slot is inferred
from duration, admission caps, review rounds, or the cost heuristic.

A caller can opt in by supplying `EstimateRequest.token_prior`, validated as a
`LocalTokenPrior` from `agent_estimate.contract.schema`. It requires:

- `basis: local-policy` explicitly;
- at least one nonnegative integer count, `expected_tokens_total` or
  `expected_tokens_output`; an absent count remains null, while zero is a count;
- nonempty `source` and `population` descriptions;
- `as_of`, a calendar date in `YYYY-MM-DD` format.

When both counts exist, output must not exceed total. The prior adds a mandatory
population mismatch warning: its population may not match the current task and
execution profile, and it is not calibrated. Omitting `warnings` adds that warning;
supplying an empty or replacement warning is rejected. A PR-leg aggregate cannot
be divided into task-level evidence. Dated and sourced means attributable, not
measured or calibrated for this task.

The typed `ForecastRecord.tokens` block keeps token provenance separate from
duration's `basis: expected-wall`. JSON reports include the token block under
`forecast.tokens` only when opted in; full and compact Markdown report both slots,
their labels and the warning. With no prior, CLI and Action report output is
unchanged. The package never discovers a prior file automatically.

## Rate-shape example only — not calibrated

A caller may organize its own policy by task category and a **work-minute band**:

| Key | Caller-owned policy values |
| --- | --- |
| Task category × work-minute band × execution profile | Total processed tokens per work minute; output tokens per work minute; source; date; population |

The symbolic shape is:

```text
total_count = caller_total_rate(category, work_minute_band, profile) × caller_work_minutes
output_count = caller_output_rate(category, work_minute_band, profile) × caller_work_minutes
```

This is an example shape only, **not calibrated**, and ships no numeric rates or
`token_priors.yaml`. Bands use explicit minutes; bare size letters are ambiguous.
The caller chooses any rate, minute basis and rounding policy, then submits the
resulting integer counts and provenance. Agent-estimate neither implements this
rate calculation nor chooses a band, rescales a PR-leg aggregate, or supplies a
population match. Its v0.8 path validates and reports the supplied counts.

Measured correction, task-bound actuals ingestion and runtime-log readers belong
to later work. No measured or calibrated token basis is accepted here.

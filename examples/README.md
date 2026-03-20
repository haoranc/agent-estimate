# Examples

Real input/output examples from production agent dispatches. Every command below is copy-paste runnable after `pip install agent-estimate`. Each example includes a "What actually happened" section showing the real dispatch outcome.

| Example | Task type | Tier | Compression | File |
|---------|-----------|------|-------------|------|
| Fix pyproject URLs after org rename | Coding | XS | 2.00x | [coding-s.md](./coding-s.md) |
| Implement CLI command with code generation | Coding | M | 2.53x | [coding-m.md](./coding-m.md) |
| Audit cloud infrastructure providers | Research | S | 2.61x | [research.md](./research.md) |
| Write quickstart guide + README | Documentation | S | 2.58x | [documentation.md](./documentation.md) |
| 3-agent parallel session (3 features) | Multi-agent | M×3 | 7.60x | [multi-agent.md](./multi-agent.md) |

## How to read the output

- **Tier** — task size: XS (~10m), S (~24m), M (~52m), L (~100m), XL (~195m)
- **PERT (O/M/P)** — optimistic / most-likely / pessimistic estimates, weighted to expected
- **Human Equivalent** — how long this would take a human developer (task-type-specific multiplier)
- **Compression ratio** — human time / agent time. Higher = more agent leverage.
- **Wave** — parallel scheduling group. Tasks in the same wave run concurrently.
- **METR warning** — fires when an estimate exceeds the model's reliability threshold
- **What actually happened** — real dispatch data showing estimate vs actual outcome

## Calibration data

These examples are drawn from a production multi-agent fleet (Claude, Codex, Gemini) running real development tasks. Key stats from the calibration dataset:

| Metric | Value |
|--------|-------|
| Validated dispatches | 149+ |
| Total dispatches tracked | 190+ |
| M-tier accuracy | Expected case within ±20% |
| Task types covered | Coding, research, documentation, brainstorm, config |
| Agents calibrated against | Claude Code (Opus 4.6, High thinking), Codex (GPT-5.4, Extra High thinking) |

Estimates improve with calibration data. Use `agent-estimate validate` to feed your own dispatch outcomes back into the model.

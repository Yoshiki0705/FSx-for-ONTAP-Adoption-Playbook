# Current vocabulary findings

This is an English, nonlocalized current-state report for the required public-output vocabulary check.

## Current state

The full tracked prose tree has zero `sales-vocabulary` findings. The category is included in the default `make audit` path and is therefore required by the commit and pull-request gate.

Exact external titles that contain a detected term retain their published wording with a line-level `allow:sales-vocabulary` marker. `make allow-budget` verifies that each marker suppresses a finding and that the reviewed allowance set has not changed.

## Reproduction

Run from the repository root:

```bash
make vocabulary-report
make audit
make allow-budget
```

`make vocabulary-report` remains informational and returns success after printing any findings. `make audit` fails when the default required categories contain a finding.

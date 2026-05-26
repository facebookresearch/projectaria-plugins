---
name: vrs-health-check
description: Use when working with VRS Health Check — validating Aria recording quality before MPS processing. Covers the run_vrs_health_check CLI, configurations, threshold checks, exit codes, overriding thresholds, and the Python API. Use whenever the user mentions VRS health check, recording validation, data quality checks, dropped frames, or pre-MPS validation.
---

# VRS Health Check

VRS Health Check validates Aria recording quality — checking for dropped frames, sensor consistency, calibration validity, and timing issues. It runs automatically as part of MPS processing, but can also be run standalone to diagnose recording problems before submission.

## How to Use This Skill

This skill teaches concepts. For details:

- **CLI**: `run_vrs_health_check --help`
- **Configurations and checks**: https://facebookresearch.github.io/projectaria_tools/gen2/ark/vrs_health_check/configuration_and_thresholds
- **Threshold customization**: https://facebookresearch.github.io/projectaria_tools/gen2/ark/vrs_health_check/customization
- **Python API**: `from projectaria_vrs_health_check import vrs_health_check`, then `help(vrs_health_check)`

## Installation

- **Install**: `pip install projectaria-vrs-health-check` (also installed automatically with `projectaria-mps`)
- **CLI command**: `run_vrs_health_check`
- **Docs**: https://facebookresearch.github.io/projectaria_tools/gen2/ark/vrs_health_check/installation

## Capabilities Overview

### Configurations

Multiple preset configurations exist for different device generations and use cases (e.g. general-purpose vs SLAM-focused with stricter thresholds). Run `--list-configurations` to see all available presets, and `--show-configuration-json <name>` to inspect all checks and thresholds for a configuration.

**Key concept**: All available configurations are evaluated during every run regardless of which one you select with `--choose-configuration`. The selected configuration controls the exit code and console output, but the JSON output contains results for all configurations.

### Check Types

Two types of checks:

- **Numeric checks**: Compare measured values (frame rates, drop ratios, timing deviations) against `warn_threshold` and `fail_threshold` values. Supports duration-dependent thresholds that relax for short recordings.
- **Boolean checks**: Verify true/false conditions (calibration validity, file integrity).

Each check produces PASS, WARN, or FAIL. Use `--show-configuration-json` to discover all check names and their thresholds.

### Exit Codes

| Code | Meaning | MPS Implication |
|------|---------|-----------------|
| `0` | PASS | Good for MPS processing |
| `1` | WARN | Minor issues, MPS likely still works |
| `2` | FAIL | Fix before MPS processing |
| `64` | Usage error | CLI invocation problem |
| `66` | No input | File not found |

**WARN guidance**: Small numbers of dropped frames (3-5%) are marginal but usually processable. IMU warnings with camera pass usually means MPS will still succeed — MPS relies more heavily on cameras.

### Overriding Thresholds

Two methods to customize thresholds — useful when default thresholds are too strict or too lenient for your use case:

- **Command line**: `--override-checks` with the pattern `"CheckGroup.metric.threshold_type=value"`
- **JSON file**: `--override-check-file` for complex, reusable custom configurations

Both require `--configuration-to-override` to specify the base config. Use `--show-configuration-json` to discover valid check group and metric names. Checks can also be disabled entirely with `ignore=true`. See the customization docs for syntax and examples.

### Python API

The health check is also available as a Python function for programmatic use and batch processing:

```python
from projectaria_vrs_health_check import vrs_health_check
```

Run `help(vrs_health_check.run_vrs_health_check)` for the function signature and parameters.

## Relationship to MPS

VRS health check runs automatically as the first stage of MPS processing. A FAIL result blocks MPS from proceeding. Running health check standalone lets you diagnose and fix recording issues before uploading to MPS, saving time on the upload/processing cycle.

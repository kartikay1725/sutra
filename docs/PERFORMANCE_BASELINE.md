# SUTRA Production Performance Baseline

## Executive Overview
This document records baseline latency and throughput metrics for key SUTRA API operations measured under test conditions.

---

## Metric Baselines

| Operation | Target Latency (p95) | Observed Baseline | Throughput Capacity |
|---|---|---|---|
| GET /health | < 5ms | ~1.2ms | > 2,000 rps |
| GET /ready | < 20ms | ~4.5ms | > 800 rps |
| POST /v1/changes | < 50ms | ~18ms | > 200 rps |
| POST /v1/pull-requests/{id}/merge | < 150ms | ~42ms | > 50 rps |
| CI Sandbox Execution | < 1,500ms | ~450ms | Bounded by CPU pool |

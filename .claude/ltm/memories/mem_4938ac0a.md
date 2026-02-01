---
id: "mem_4938ac0a"
topic: "IPv6 localhost curl connection reset fix"
tags:
  - networking
  - curl
  - ipv6
  - ipv4
  - localhost
  - container
  - debugging
phase: 0
difficulty: 0.6
created_at: "2026-02-01T14:17:22.069764+00:00"
created_session: 16
---
## Problem
When hooks use `curl -s -X POST http://localhost:PORT/...`, the connection fails with "Connection reset by peer" on systems where `localhost` resolves to IPv6 (`::1`) first.

## Cause
The container listens on `0.0.0.0` (IPv4) but curl connects to `::1` (IPv6) when using `localhost`.

## Solution
Use `127.0.0.1` explicitly instead of `localhost` in all hook URLs:
```bash
# Bad - may fail on IPv6-first systems
curl -s -X POST http://localhost:29470/hook/session_start

# Good - explicitly uses IPv4
curl -s -X POST http://127.0.0.1:29470/hook/session_start
```

## Diagnosis
```bash
# This fails (IPv6)
curl -v http://localhost:29470/health
# Output: Trying [::1]:29470... Connection reset by peer

# This works (IPv4)
curl -4 http://127.0.0.1:29470/health
# Output: {"status": "healthy", ...}
```

# ADR 0007: First apps in Python, started locally without Docker

Status: accepted (3 November 2026)

## Decision
The reference DESP (`apps/desp`) and the bank back-end (`apps/psp`) are written in Python 3.11+ with Starlette and uvicorn (web server), httpx (outgoing calls) and jsonschema (contract checks). They are started locally with `python3 tools/run_local.py`, without Docker.

## Why
Python is easy to read for newcomers, and the existing tools (`generate_examples.py`, `validate.py`) already use it. Starlette is the small web framework that FastAPI is built on. We planned FastAPI, but used Starlette directly: it was the package available when the first apps were built, and the apps validate every body against `/contracts` anyway, so FastAPI's own validation models would duplicate the contracts. Moving to FastAPI later is a small change. Plain processes start in a second and need nothing but `pip install`.

## Consequences
- Each app has its own pinned `requirements.txt`. Apps share no code; small helpers are copied on purpose (CONTRIBUTING.md).
- Other apps (banking app, merchant gateway, a second bank) may use any language, as long as they speak the contracts.
- A Docker Compose setup may come later, e.g. for the network relay and the observer. It should start the same apps with the same ports.

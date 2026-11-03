# Central platform (DESP)

**Run by:** Eurosystem

**Does:** Access management (users, DEANs, aliases), alias lookup, settlement engine, central ledger, DCA simulator. Later: token service, fraud scoring, disputes, data exchange.

**Offers interfaces:** I3 (DESP API, 14 endpoints in the spec), I4

**Uses interfaces:** I3 (calls the PSP API of every bank)

The only place digital euro balances live. Holds no names.

## Status

First working version (Python, [ADR 0007](../../docs/decisions/0007-first-apps-python.md)). Plays all six flows in `/examples`; checked by `tools/e2e_flows.py`.

## Run

```bash
pip install -r apps/desp/requirements.txt
cd apps/desp && python3 app.py          # http://127.0.0.1:8000
```

Usually you start everything at once with `python3 tools/run_local.py` (see the main README).

Settings (environment variables): `DESP_PORT` (8000), `DESP_PARTICIPANTS` (participant register file, default `config/participants.json`), `SIM_SEED` (test data, default `examples/test-data.json`), `DESP_FORWARD_TIMEOUT` (seconds to wait for the payee bank, 10), `SIM_LOG_FORMAT=json` (print full log events).

## Endpoints

| Endpoint | What | Basis |
|---|---|---|
| `POST /v1/payment-instructions` | Payment from the payer's bank, optionally with a funding part (reverse waterfall) or, at the same bank, a defunding part (waterfall) | D2-7 p.57–64 |
| `POST /v1/fundings`, `POST /v1/defundings` | Standalone funding / defunding | D2-7 p.49–57 |
| `POST /v1/sim/alias-lookup` | Phone number → DEAN + bank | **placeholder** (INTERPRETATION T5) |
| `GET /sim/state` | Ledger entries, DCA balances, money check, access data, last transactions | simulation only |
| `GET /sim/events?since=N` | The message log (see below) | simulation only |
| `POST /sim/reset` | Back to the test data | simulation only |
| `GET /health` | Health check | simulation only |

Calls on each bank's PSP API: the forwarded `POST /v1/payment-instructions` (only when payer and payee banks differ) and the status pushes `POST /v1/payment-instructions/{id}/status`, `/v1/fundings/{id}/status`, `/v1/defundings/{id}/status` (the bank answers 204).

## How it works

1. A bank sends an instruction. The DESP checks the technical header (T1) and the body against the contract schema. Invalid → HTTP 400 `application/problem+json` (T10).
2. It answers **201** at once: `AcceptedTechnicalValidation`, or `Rejected` with a reason if a check from INTERPRETATION T11 fails (then no status push follows, D2-7 Fig. 6).
3. In the background: if the payee is at another bank, it forwards the instruction **without the payer's ledger entry** and takes the payee's entry (and maybe a `paymentDefundingObject`) from that bank's 201.
4. It settles **all legs in one atomic step** (`ledger.py`): funding (DCA → payer), payment, defunding (payee → DCA). If any leg fails, nothing is booked.
5. It pushes the final status to every bank involved. Funding ID/status go only to the payer's bank, defunding ID/status only to the payee's bank (T7). If the payee bank rejected, only the payer's bank gets a status (D2-7 Fig. 8).

Ledger: one balance per entry and one DCA per bank (BIC). Funding debits the DCA of `instructedAgent`, defunding credits it (T4). Money check in `/sim/state`: digital euro in circulation = opening balances + net DCA debits since start.

## Code

| File | What |
|---|---|
| `app.py` | Routes, start-up, seeding |
| `settlement.py` | Checks, forwarding, atomic settlement, status pushes |
| `ledger.py` | Entries, DCAs, atomic booking, money check |
| `access.py` | Participant register (config) and Access Management (alias → DEAN → bank, entry) |
| `http_util.py` | Technical headers, problem+json, logging of every HTTP message |
| `sim_log.py` | **The one place** where log events are produced (printed now; later sent to the relay / observer, I6) |
| `schema_check.py` | Validation against `/contracts` |
| `reasons.py`, `sim_ids.py` | Reason codes (C8), IDs and amounts |

## Placeholders and simplifications

- Alias lookup and the alias/DEAN registry: placeholder (T5). Seeded from `examples/test-data.json`; no onboarding calls yet.
- Reason codes starting with `X`: placeholders (C8, table in INTERPRETATION).
- `settlementBusinessDay` = today's UTC date (no real DCA business day).
- No retries, no status queries, no idempotency beyond rejecting a reused UETR (`XDUP`).
- Payee-initiated payments, refunds, reservations, reports: not built yet.
- State lives in memory; a restart starts again from the test data.

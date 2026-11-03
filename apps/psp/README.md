# Bank back-end (PSP)

**Run by:** each bank

**Does:** Customers and KYC (test persons), customer↔DEAN link, balance and holding-limit checks, waterfall / reverse waterfall, payment initiation, giro accounts (core banking stand-in).

**Offers interfaces:** I1 (for its banking app), I3 PSP API (10 endpoints in our setup)

**Uses interfaces:** I3 (DESP API)

One template, run once per bank (PSP A, PSP B, …) with its own configuration ([ADR 0006](../../docs/decisions/0006-banks-and-merchants.md)).

## Status

First working version (Python, [ADR 0007](../../docs/decisions/0007-first-apps-python.md)). Plays all six flows in `/examples`; checked by `tools/e2e_flows.py`.

## Run

```bash
pip install -r apps/psp/requirements.txt
cd apps/psp
python3 app.py config/psp-a.json        # PSP A, SIMADEF0XXX, http://127.0.0.1:8001
python3 app.py config/psp-b.json        # PSP B, SIMBDEF0XXX, http://127.0.0.1:8002
```

Usually you start everything at once with `python3 tools/run_local.py` (see the main README). A new bank = a new config file plus an entry in the DESP's participant register (`apps/desp/config/participants.json`) and customers in the test data.

Settings (environment variables, override the config file): `PSP_PORT`, `DESP_URL`, `SIM_SEED` (test data), `PSP_STATUS_TIMEOUT` (seconds to wait for the final status, 15), `SIM_LOG_FORMAT=json`.

## Endpoints

| Endpoint | Called by | What | Basis |
|---|---|---|---|
| `POST /i1/messages` | banking app | Payment initiation, online funding / defunding request | D1-1 §8.1.1.6, §7.1.1.1; A1 |
| `POST /v1/payment-instructions` | DESP | Forwarded payment: we are the payee's bank | D2-7 p.102–106 |
| `POST /v1/payment-instructions/{id}/status` | DESP | Final status → 204 | D2-7 p.106–109 |
| `POST /v1/fundings/{id}/status`, `/v1/defundings/{id}/status` | DESP | Final status → 204 | D2-7 p.95–102 |
| `POST /sim/holding-limit` | game master | `{"command": "SET_HOLDING_LIMIT", "amount": {...}}` | simulation only (ADR 0005) |
| `GET /sim/state` | anyone | Customers: name, DEAN, giro, blocked, digital euro | simulation only |
| `GET /sim/events?since=N`, `POST /sim/reset`, `GET /health` | anyone | Log, reset to test data, health | simulation only |

Every I1 request needs the header `Sim-User-DEAN` with the logged-in customer's DEAN (**placeholder** for the app's login after SCA, INTERPRETATION A12). Without it: 401 problem+json.

## What the bank does

**As payer's bank** (I1 payment initiation):
1. Alias lookup at the DESP (placeholder), or the DEAN given by the app.
2. Balance check. If the digital euro balance is too low: **reverse waterfall**. Block the missing amount on the giro account, add a `fundingObject` with our own BIC and no encrypted part (T3). Not enough on the giro account either → rejected with `XBAL` before anything is sent.
3. Same bank: both ledger entries in clear, no encrypted part; a `defundingObject` if the payee would exceed the holding limit. Different banks: payee details only in the encrypted part (`SIMENC:` + base64, C7), no payee entry.
4. UETR = UUID v7 (C5). The bank registers the UETR **before** sending, so a status push that arrives early is not lost.
5. Waits for the final status push (A7), then debits the blocked giro amount (or releases it on rejection) and answers the app: `ReturnCode` 0, or 1 + `StatusReason` (A13).

**As payee's bank** (forwarded instruction): decrypts the party details, finds the customer by DEAN, answers 201 `AcceptedCustomerProfile` with the customer's ledger entry and, if balance + amount > holding limit, a `paymentDefundingObject` (waterfall, LM-050-002). After the settled status it credits the swept amount to the giro account (A11).

**Funding / defunding** (I1 online request): funding blocks the giro amount first and debits it after the settled status; defunding credits the giro account after the settled status (A11).

## Code

| File | What |
|---|---|
| `app.py` | Routes, configuration, I1 envelope |
| `payer.py` | Payer side: payment, funding, defunding |
| `payee.py` | Payee side: forwarded payment instructions, waterfall |
| `customers.py` | Customers and the core banking stand-in (giro block / debit / release / credit) |
| `desp_client.py` | Calls to the DESP API |
| `waiting.py` | Transactions waiting for their final status (by UETR) |
| `http_util.py`, `sim_log.py`, `schema_check.py`, `sim_ids.py`, `reasons.py` | Same jobs as in the DESP (copied, apps share no code). `sim_log.emit()` is the one place where log events are produced |

## Placeholders and simplifications

- `Sim-User-DEAN` login header (A12) and the alias lookup call (T5) are placeholders.
- Waterfall and reverse waterfall are switched on for every test user (the D1-1 liquidity settings are not built yet).
- The bank keeps its own copy of each customer's digital euro balance, updated from the DESP's status pushes. There is no balance query to the DESP yet.
- The holding limit is one value per bank, set by config or the game master (ADR 0005), not per customer.
- The payee name (`Name`, A14) goes into the encrypted part as typed by the user; it is not checked.
- Only P2P (`PP01`, MCC 4829) with `ALIA` or `DEAN` as payment method. No notification to the payee's app yet.
- State lives in memory; a restart starts again from the test data.

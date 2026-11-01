# Contracts

Contract version: **0.1.0** (draft)

This folder defines how the apps talk to each other. An app is compatible if every message it sends validates against these schemas and it accepts every message described here.

| Folder | Interface | Status |
|---|---|---|
| `common/` | Shared data types from the ECB data dictionary (D2-8) | draft |
| `i1-app-psp/` | I1 · banking app ↔ its bank (ECB Annex D1-1) | payment initiation + response |
| `i3-psp-desp/` | I3 · bank ↔ central platform (ECB Annex D2-7) | payment instructions, both directions |
| `i6-observer-events/` | I6 · relay → observer (ours) | idea only |
| `i7-game-master/` | I7 · game master → all apps (ours) | idea only |
| `INTERPRETATION.md` | Every choice we made where the spec is open | **read this first** |

Schemas are JSON Schema 2020-12. Their `$id`s use the placeholder host `digital-euro-simulator.invalid`; `tools/validate.py` resolves them locally.

## Covered so far

| Message | Direction | Schema |
|---|---|---|
| Individual user payment initiation | app → bank | `i1-app-psp/schemas/payment-initiation.request.schema.json` |
| Outgoing envelope | bank → app | `i1-app-psp/schemas/response.schema.json` |
| `POST /v1/payment-instructions` | bank → DESP | `i3-psp-desp/schemas/desp-api/…request…` + `…response-201…` |
| `POST /v1/payment-instructions` (forwarded) | DESP → payee bank | `i3-psp-desp/schemas/psp-api/…request…` + `…response-201…` |
| `POST /v1/payment-instructions/{id}/status` | DESP → each bank | `i3-psp-desp/schemas/psp-api/post-payment-instruction-status.request.schema.json` |
| Content of the encrypted payment part | bank → bank via DESP | `i3-psp-desp/schemas/encrypted-payment-instruction-content.schema.json` |

## Next

Fundings and defundings (manual load and unload), payee-initiated payments (`POST /v1/payments`), status queries, refunds, balance query, and placeholder onboarding calls. The full list of I3 endpoints is in `docs/spec-notes/settlement-catalogue.md`.

# I3 · Bank ↔ central platform (DESP)

Based on ECB Annex D2-7 (Settlement), D2-1 (Introduction and exceptions), D2-8 (Data dictionary). REST with JSON, both directions:

- **DESP API**: offered by the central platform, called by banks (14 endpoints in the spec).
- **PSP API**: offered by **every bank**, called by the central platform (12 endpoints in the spec; 10 needed here, because open funding/defunding never happens, see ADR 0001).

## Pattern

1. A bank sends an instruction; the platform answers right away with **201** (received, technically checked).
2. If another bank is involved, the platform forwards the instruction; that bank answers **201** and adds its part (e.g. the payee's ledger entry).
3. The platform settles everything in one atomic step.
4. It pushes the final status to every bank involved; each answers **204** (no body).

## What the platform can read

Clear text: bank codes, amount, payment type, ledger entries, UETR, timestamps, statuses. Encrypted for the other bank (and only sent between different banks): DEANs, names, IBANs, payment text. Each bank only receives its own customer's ledger entry.

## Technical header

See `contracts/INTERPRETATION.md`, choice T1.

## Errors

Business rejection: status `Rejected` plus `statusReason` (e.g. `AC05` account closed, `AC06` account blocked, `AB03` settlement timeout, `D005` PSP not a participant). Technical errors: HTTP 4xx/5xx with an `application/problem+json` body (D2-1): `type`, `status`, `title`, `detail`, `instance`, `reasonCode`, `additionalErrors[]` (schema `common/problem.schema.json`, INTERPRETATION T10). Which check leads to which answer: T11.

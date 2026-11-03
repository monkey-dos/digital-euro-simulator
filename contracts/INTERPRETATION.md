# Interpretation choices

Where the ECB documents are silent, ambiguous or contradict each other, we make **one** choice and record it here. Anyone building an app follows these choices, so all apps stay compatible. Change a choice only through a pull request that also updates schemas and examples.

Sources: Rulebook v0.91; Annex D1-1 (Distributing PSP requirements); D1-7 (Data management); D2-1 (Introduction and exceptions); D2-6 (Data exchange); D2-7 (Settlement); D2-8 (Data dictionary). All drafts dated 2 July 2026.

## Common

| # | Topic | What the spec says | Our choice |
|---|---|---|---|
| C1 | Status values in JSON | D2-8: "For all codes used in JSON structures … the name of the code is used as a value." | `AcceptedTechnicalValidation`, `AcceptedCustomerProfile`, `AcceptedSettlementCompletedDebitorAccount`, `Received`, `Rejected` (not ACTC etc.). |
| C2 | `…TransactionStatus` fields | D2-7 types them as `TransactionStatus`, which D2-8 defines as `{status, statusReason}`; the messages also carry a separate `statusReason`. | Object form `{"status": "…"}`. The root `statusReason` is used for the reason; the nested one stays empty. |
| C3 | Payment type values | D2-8 lists PP01, PB01, BP01, FU01, DF01; the "name" rule (C1) is ambiguous for these. Annex A example uses `"P2P"`. | 4-letter codes (`PP01` …). |
| C4 | Ledger entry | D2-8: attribute "Entry ID", type "Tbd". | `{"entryId": "ENT-<12 hex>"}`, opaque. Access Management keeps the link entry ↔ DEAN. **Placeholder.** |
| C5 | UETR version | D2-8: UUID v7. D1-1 says the payer PSP generates a UUID v4. | UUID v7 (back-end data dictionary wins). |
| C6 | Amount | D2-8: string, dot decimal, up to 14 significant figures. D1-1 (app side): number. | I3: `{"currency":"EUR","amount":"50.00"}`. I1: number `50.00` + separate `Currency`. |
| C7 | Encryption of party data | D2-7 names `encrypted…Object` fields but no method; Annex A (informative) hints at key + ciphertext. | **Simulated**: `"SIMENC:" + base64(JSON)`. Not secure, on purpose, so the observer can show the content. Example files add a `decryptedView` next to the wire body. |
| C8 | Reason codes | Only a few named in D2-1 (AC05, AC06, AB03, ARFR, D002, D005); D1-1 refers to D1-5 (not available). | Use those where they fit; anything else is a placeholder code starting with `X`. |
| C10 | Date-time format | D2-8: ISODateTime; UTC or UTC offset "strongly recommended", local time allowed. | Always UTC (`Z`) or an explicit offset; local time without offset is rejected. |
| C9 | Test BICs | – | `SIMADEF0XXX` (PSP A), `SIMBDEF0XXX` (PSP B). Fictional. |
| C11 | Test IBANs (giro accounts) | – | German format with valid check digits and bank code `00000001`, which belongs to no real bank. |

## I3 · Bank ↔ central platform

| # | Topic | What the spec says | Our choice |
|---|---|---|---|
| T1 | Technical header | D2-1: Request ID (UUID), Request timestamp, Requesting agent (BIC, only bank → DESP); responses: Request ID, Response timestamp. No HTTP header names given. | HTTP headers `Request-Id`, `Request-Timestamp`, `Requesting-Agent`; responses `Request-Id`, `Response-Timestamp`. |
| T2 | Base path | D2-7 uses `/v1/…`, sometimes without the prefix. | Always `/v1/…`. |
| T3 | Open funding / defunding | Allowed by the spec. | Never used (ADR 0001); no `encryptedFundingObject` / `encryptedDefundingObject`. |
| T4 | Which DCA is debited on funding | Not named in any message. | The DCA of the bank in `instructedAgent`. |
| T5 | Alias lookup and onboarding calls | Only referenced (`GET /users/{userID}`, `PUT /deans`); spec in a document we don't have. Rulebook §4.4.3 p.99 names an Alias Lookup Service of the DESP. | Placeholder steps, marked `"placeholder": true`, field names borrowed from the D2-6 account data query. Alias lookup: `POST /v1/sim/alias-lookup`, request `{proxyAlias, proxyAliasType}`, 200 response `{DEAN, digitalEuroPspId}`, technical headers as T1; unknown alias → 404 problem+json (T10) with `XALI`. Schemas in `i3-psp-desp/schemas/placeholder/`. The DESP's Access Management keeps alias → DEAN → (bank, ledger entry); in the simulation this is seeded from `examples/test-data.json`. **Placeholder.** |
| T6 | `UETR` presence | D2-8: optional; D2-7: mandatory for all transactions. | Mandatory. |
| T7 | Defunding status in a waterfall between two banks | D2-7 p.16: defunding ID and status are received only by the payee's digital euro PSP and the payee's commercial bank money PSP; p.108: mandatory in the status push if the request had a defunding object. Fig. 13 sends a separate `POST /defundings/{id}/status` to the commercial bank money PSP when it is a different bank; in Fig. 11 (all roles at one bank) the status travels inside the payment-instruction status push. | The payee's bank is both roles (ADR 0001), so it gets `defundingStatus`/`defundingId` inside the payment-instruction status push and no separate call. The payer's bank gets neither. |
| T9 | `fundingId` / `defundingId` in a rejected 201 | D2-7 p.52/p.56 mark the ID mandatory; p.16 says it is present only if validation is positive. | Required only when the status is not Rejected. |
| T8 | Status in the DESP 201 for a standalone funding/defunding | Allowed: Rejected, AcceptedTechnicalValidation, AcceptedCustomerProfile. | `AcceptedTechnicalValidation`, as for payment instructions. |
| T10 | Technical errors | D2-1 lists type, status, title, detail, instance, a reason code and additional errors for `application/problem+json`, without key names for the last two. | Keys `reasonCode` and `additionalErrors[]` (`location`, `detail`); schema `common/problem.schema.json`. Used for HTTP 400 (body or header invalid), 401 (I1, no user, A12) and 404 (unknown alias, T5). A business rejection is never a 4xx: it is a 201 with status `Rejected`. |
| T11 | Which checks the DESP makes when | D2-7: the 201 reports technical validation; settlement verification happens later (p.10). | **In the 201** (status `Rejected`, no status push, Fig. 6): bank not a participant (`D005`), `Requesting-Agent` differs from `debtorAgent`/`instructingAgent`, `creditorEntry`/encrypted part present or missing against the same-bank rule, open funding/defunding (`XNSU`), amount not positive, UETR already used (`XDUP`). **At settlement** (status push `Rejected`): ledger entry unknown or held via another bank (`XACC`), balance too low (`XBAL`), DCA too low (`XDCA`), payee bank rejects (its reason), answers invalidly (`XFWD`) or not in time (`AB03`). If the payee bank rejects, only the payer bank gets a status push (Fig. 8). Also rejected in the 201: debtorEntry = creditorEntry (`XACC`). The participant check (`D005`) comes first, so an unknown requesting bank learns that it is not a participant. |
| T12 | `settlementBusinessDay` in the payment status push | D2-7 p.72–73, p.108: mandatory only if the instruction had a funding or defunding part; the schema requires it together with `settlementDateTime` on success. | Always sent with a settled status, also without funding/defunding, as in the examples: one rule for all pushes, and the field is allowed in every case. In the simulation it is today's UTC date. |

## I1 · Banking app ↔ its bank

| # | Topic | What the spec says | Our choice |
|---|---|---|---|
| A1 | Transport | D1-1 defines message content, not transport. | `POST /i1/messages` with JSON; the response comes back on the same call. |
| A2 | Key names | D1-1 gives "standardised names" (ISO 20022 style). | Use them as JSON keys, e.g. `MessageIdentification`. |
| A3 | Transaction date | Standardised name `CreationDateTime`, which clashes with the envelope field of the same name. | Key `TransactionDate`. |
| A4 | Payee DEAN | No standardised name. | Key `PayeeDEAN`. |
| A5 | Payment method codes | STR 4, "code set to be clarified". | `QRCD`, `LINK`, `ALIA`, `DEAN`, `NFCP`. **Placeholder.** |
| A6 | Alias type for phone numbers | ISO `ExternalProxyAccountType1Code`. | `TELE`. **To be verified** against the ISO list. |
| A7 | When the bank answers the app | Not fixed. | After the final settlement status. |
| A8 | `ReturnCode` | BOOL, 0 = successful, 1 = failure. | Integer `0` / `1`. |
| A9 | Funding/defunding request: account types | D1-1 §7.1.1.1 uses the standardised name `CashAccountType` for both the debited and the credited account. | Keys `DebtorCashAccountType` and `CreditorCashAccountType`. |
| A10 | Funding/defunding request: DEAN field | "Digital euro account number", standardised name "(New for digital euro)". | Key `DigitalEuroAccountNumber`. |
| A11 | When the bank debits or credits the giro account | D1-1 §7.2 lists blocking, debit, credit and release without an order. Rulebook LM-040-003 and LM-050-003: credit the giro account immediately after DESP confirms settlement (defunding, waterfall). | Funding: block before sending to DESP, debit after the settled status. Defunding and waterfall: credit after the settled status. |
| A12 | Who is logged in | D1-1 assumes the user has passed strong customer authentication (SCA) in the app; how the app proves this to its bank is not specified. | **Placeholder:** HTTP header `Sim-User-DEAN` with the logged-in user's DEAN on every I1 request. Missing or unknown → 401 problem+json (T10) with `XAUT`. Stands in for a real session or token after SCA. |
| A13 | Errors on I1 | D1-1: `ReturnCode` 1 + `StatusReason` on failure. | Business rejections (also those coming back from the DESP): HTTP 200, `ReturnCode` 1, `StatusReason` = the reason code. Invalid request body: 400 problem+json (T10). `XTMO` means the outcome is unknown (settlement may have happened); the app should not retry blindly but check the balance. |
| A14 | Payee name in a payment initiation | D1-1 lists `Name` (payee name) in the payment initiation. | The app sends the name the user typed or picked from contacts. The bank copies it into `creditor.name` of the encrypted part and does not check it. |

## Placeholder reason codes (C8)

Codes from the ECB documents: `AB03` (timeout), `AC05` (account closed), `AC06` (account blocked), `D005` (bank not a participant). Our placeholders, all starting with `X`:

| Code | Meaning |
|---|---|
| `XFMT` | Message format, schema or consistency error |
| `XHDR` | Technical header missing or invalid (T1) |
| `XAUT` | No logged-in user on I1 (A12) |
| `XACC` | Account or ledger entry unknown, or held via another bank |
| `XBAL` | Balance too low (digital euro, plus giro account where reverse waterfall applies) |
| `XDCA` | The bank's DCA has not enough central bank money |
| `XLIM` | Funding would exceed the holding limit |
| `XNSU` | Not supported in this simulation (e.g. open funding, ADR 0001) |
| `XFWD` | The other bank gave an invalid answer |
| `XALI` | Alias not registered |
| `XDUP` | UETR already used |
| `XNET` | The bank could not reach the DESP; nothing was sent, all blocks are released |
| `XTMO` | Outcome unknown: the bank sent the instruction but got no answer or no final status in time. Settlement may still have happened; a late status push is still booked |
| `XINT` | Internal error in an app (a bug) |

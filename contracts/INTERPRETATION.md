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

## I3 · Bank ↔ central platform

| # | Topic | What the spec says | Our choice |
|---|---|---|---|
| T1 | Technical header | D2-1: Request ID (UUID), Request timestamp, Requesting agent (BIC, only bank → DESP); responses: Request ID, Response timestamp. No HTTP header names given. | HTTP headers `Request-Id`, `Request-Timestamp`, `Requesting-Agent`; responses `Request-Id`, `Response-Timestamp`. |
| T2 | Base path | D2-7 uses `/v1/…`, sometimes without the prefix. | Always `/v1/…`. |
| T3 | Open funding / defunding | Allowed by the spec. | Never used (ADR 0001); no `encryptedFundingObject` / `encryptedDefundingObject`. |
| T4 | Which DCA is debited on funding | Not named in any message. | The DCA of the bank in `instructedAgent`. |
| T5 | Alias lookup and onboarding calls | Only referenced (`GET /users/{userID}`, `PUT /deans`); spec in a document we don't have. | Placeholder steps, marked `"placeholder": true`, field names borrowed from the D2-6 account data query. |
| T6 | `UETR` presence | D2-8: optional; D2-7: mandatory for all transactions. | Mandatory. |

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

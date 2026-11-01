> Machine-generated reading notes for the digital euro simulator (Nov 2026). Always check names and fields against the original ECB document before relying on them.

# Settlement service catalogue (DESP <-> PSP)

Source: ECB, *Digital Euro Scheme Rulebook v0.91 (DRAFT, 02/07/2026), Annex D2 – Back-end implementation specification #7 – Settlement*, 174 pages.
Page numbers below ("p.") are the printed page numbers ("PAGE x OF 174").
Field names are quoted exactly as written in the spec, including typos. Where something is our own reading and not stated in the spec, it is marked **[our inference]**. Where the doc refers to a different document, that is said explicitly.

Cross-checked against: Annex D2 #8 *Data dictionary* (`data_dictionary.txt`), Annex D2 #6 *Data exchange* (`data_exchange.txt`), and the rulebook main text (`rulebook.txt`). Facts taken from those are marked **[DD]**, **[DX]** or **[RB]**.

> The doc's own notice (p.1): "This rulebook is an interim draft ... should not be used for pilot or implementation purposes." Text highlighted in yellow in the PDF is a placeholder (p.3 preamble).

---

## 0. Scope: what this document does and does NOT contain

**Covered (main body, ch. 12):** funding, defunding, payer-initiated payment, payee-initiated payment ("request for payment"), combined payments (payment + funding = reverse waterfall, payment + defunding = waterfall), refunds (e/m-commerce only, footnote 11 p.13), payment-request status inquiry, status GETs, user-entry balance query, transactions report + report-ready notification + available-reports list.

**Annex A (p.124–174): reservations** – "v0.90 carried-over content for information only ... has not been further updated or reviewed as part of v0.91" (p.124). Footnotes 3 and 10 (p.10, p.13): reservation "is not covered in the current scope of the rulebook". Treat as **informative**.

**NOT in this document:**
- **No onboarding, user registration, DEAN creation/allocation, alias (proxy) registration, account opening/closing, holding-limit management, or emergency switching messages.** The settlement endpoints only *use* already-existing identifiers: the ledger **entry** (`userEntry`, `debtorEntry`, `creditorEntry`) in cleartext and the **DEAN** (inside the `Account reference` type, only in encrypted parts). The Data-exchange spec [DX] mentions an "Account data maintenance report" covering "DEAN (added/deactivated/deleted)" and an "Account data query" (DEAN / proxy aliases), and lists "hashed technical proof" / "user ID" as data held in DESP. So account and alias management happens in another Annex D2 spec that we do not have here.
- **No technical header definition, no technical-error (HTTP 4xx/5xx) catalogue, no idempotency rules, no encryption algorithm or key management.** Every endpoint says "Technical header: please refer to section Technical header (Introduction and exceptions management section)". That is a separate Annex D2 document (not provided). The GET /available-reports request and response instead refer to "section 5.3.3.1" (p.91–92).
- **No statusReason code list** (see §5).
- **No DCA messages** (liquidity transfers, DCA status, floor/ceiling, debit/credit notifications). [DX] (services overview): "The DCA related reports ..., queries (DCA/CMB/Liquidity transfer status) and notifications (floor/ceiling/debit/credit) will be part of separate DESP DCA documentation." [RB] §1.7: DESP DCAs "are not covered by this rulebook" and are governed by the TARGET Guidelines.
- **No offline digital euro.**

---

## 1. Conventions

### 1.1 Style, base path, versioning
- "The interface is based on RESTful API principles and the data format used is JSON" and "The data dictionary, including complex data types, is based on ISO20022 where available" (p.13).
- All endpoint tables give paths prefixed with **`/v1/`** (e.g. `POST /v1/fundings`, p.49). No host or base URL is given in the main body. Annex A only: callback server `https://{server_region}.ecb.europa.eu/v1/reservation-requests/{id}/confirmation` (p.140, p.147).
- Path parameters are kebab-case (`{funding-id}`, `{payment-instruction-id}`, `{payment-id}`, `{refund-id}`). Body fields are camelCase.
- Two API "sides", both under `/v1/` with **the same resource names**:
  - **DESP API**: exposed by DESP and called by PSPs (§12.1.3.3).
  - **PSP API**: exposed by **every PSP** and called by DESP (§12.1.3.4).
- PSPs never talk to each other directly. DESP relays everything ("facilitate the build-up of the settlement instruction without back-and-forth of messages among PSPs", p.11).

### 1.2 HTTP methods and response codes (as specified)
| Situation | Code |
|---|---|
| Positive technical validation of a *request that creates something* (POST /fundings, /defundings, /payment-instructions, /payments, /refunds, both APIs) | **201** with a body |
| Status push received (PSP API POST …/status, DESP API POST /payments/{id}/status) | **204**, no body |
| Report-ready notification received | **204** (p.123) |
| GET status / queries / reports | **200** |
| Negative technical validation | "please refer to section Technical errors (Introduction and exceptions management section)", i.e. not defined here |
| Annex A status pushes | **200 "without response body"** (p.153, p.156, p.162), which differs from the 204 in the main body |

Footnote 35/36 (p.79, p.113): if the payer PSP returns a negative technical error to a forwarded request, DESP forwards it "with problem+json if specified by the payer PSP in the synchronous response of PSP API POST /payments". This is the only mention of `application/problem+json`.

### 1.3 Technical header
Not defined in this doc. Each endpoint says: "Technical header: please refer to section Technical header (Introduction and exceptions management section)". "API specific header" is "not applicable" for all main-body endpoints. Path or query parameters are listed in an "API specific header" table with a "Path/header/query" column.

### 1.4 Synchronous / asynchronous pattern
- Footnote 16 (p.18): "Synchronous API means that the client sends a request to the server and waits until it receives the response. During this time, the client cannot perform other operations or send additional requests on the same transaction."
- **Pattern A: DESP-side settlement (single PSP or complete data):**
  1. PSP sends `POST` to the DESP API.
  2. DESP replies synchronously with `201` + resource ID + status (`ACTC`/`ACCP`/`RJCT`).
  3. After settlement, DESP pushes `POST /…/{id}/status` to the PSP API (status `ACSC`/`RJCT`).
  4. The PSP replies `204`.
- **Pattern B: forwarded request (counterparty involved):**
  1. The PSP sends the request to DESP and gets a synchronous `201`.
  2. DESP forwards a `POST` (same resource name) to the counterparty's PSP API.
  3. The counterparty answers **synchronously in the 201 response** with its validation result and its "complement settlement data". There is no separate callback.
  4. DESP settles atomically and pushes status to all involved PSPs "simultaneously".
- **Pattern C: request for payment (payee-initiated), fully relayed:**
  1. The payee PSP sends `POST /payments` to DESP.
  2. DESP forwards it to the payer PSP.
  3. The payer PSP's synchronous response is relayed back to the payee PSP as DESP's response (p.30–31: step 4 "DESP forwards the response sent in API call 3").
  4. Later the payer PSP starts Pattern B with `POST /payment-instructions`, or rejects asynchronously via `POST /payments/{payment-id}/status`.
- Atomicity: "The digital euro transactions must be settled atomically: either the whole transaction is settled, or nothing is settled" (p.10). DESP settles only once the instruction contains all parts (payment, funding, defunding) (p.10–11).
- "Exposing party" rule (p.48): "When the instructing PSP is the same PSP as the PSP instructed for payment transaction, funding transaction or defunding transaction, and the full settlement data is in the request, then the exposing party will be DESP", meaning no forwarding happens.

### 1.5 Idempotency / retries
- **Idempotency is not mentioned anywhere in this doc.**
- The only retry rule is footnote 20 (p.25): "Functional errors that come in a status message can be queried, while any other error (e.g., technical errors with HTTP code 4xx) than status after a 20x message cannot be queried. In case of a technical error, digital euro PSP can submit the same message with a new UETR after the cause is identified." So a technical rejection leaves no resource, and a retry means **a new UETR**.
- The UETR (`paymentIdentification` → `UETR`, UUID v7 [DD]) is "a unique, unalterable reference ... Set by the instructing PSP". `acceptanceDateTime` "is set by the first PSP which starts the settlement process and should not be altered by other PSPs" (e.g. p.49).

### 1.6 Encryption of party data ("encrypted…Object")
What the doc says:
- Request structure (p.13–14): "Header", "Payload: Root (UETR, acceptance timestamp and objects) / Objects".
- Payload summary table (p.15–16):

| Element | Encryption | Condition |
|---|---|---|
| UETR | Unencrypted or encrypted (fn 12: encrypted in POST /payments, POST /payments/{payment-id}/status and "GET /payments/{payment-id}/status") | Mandatory for all transactions |
| Acceptance date time | Unencrypted or encrypted (fn 13: encrypted in POST /payments, POST /payments/{payment-id}/status) | Mandatory |
| Payment Instruction object | Unencrypted | Mandatory if payment initiated by payer PSP |
| | Encrypted | "Included if payer and payee PSPs are different parties, as the content needs to be forwarded to the other PSP." |
| Payment object | Encrypted | Mandatory for a payment request initiated by the payee PSP |
| Refund object | Unencrypted / Encrypted | Same logic as the payment instruction |
| Funding object | Unencrypted | "Only required if payer's digital euro balance is lower than the transaction amount. Mandatory in case the message concerns a funding transaction." |
| | Encrypted | "Included if the digital euro and commercial bank money PSPs are different parties and the content needs to be forwarded to the other PSP." |
| Defunding object (fn 14) | Unencrypted | "Only required if the transaction results in the payee's digital euro balance exceeding payee's holding limit. Mandatory in case the message concerns a defunding transaction." |
| | Encrypted | as funding |

- Data minimisation (p.11): "the DESP forwards only the necessary information to other PSPs involved in the transaction, in line with the data minimisation principle, and collects the parts of their responses that are necessary for settlement."
- **Who encrypts:** the PSP that creates the object (instructing PSP, or the counterparty in its response).
- **Who decrypts:** the PSP the content is "forwarded to" (counterparty digital-euro PSP or commercial-bank-money PSP).
- **DESP:** the doc never explicitly says "DESP cannot decrypt". That is implied by the design (encrypted content exists only "as the content needs to be forwarded to the other PSP", and DESP works with cleartext settlement data). Algorithm, key exchange and envelope format are **not specified**. Annex A JSON examples (v0.90, informative, p.128–129) show an envelope `"fundingData": { "encryptionKey": "...", "encryptedFundingData": "..." }` and `"paymentInstructionData": { "encryptionKey": ..., "encryptedpaymentInstructionData": ... }`. This suggests a hybrid scheme (wrapped key + ciphertext), but that is v0.90 naming.
- In the main body the encrypted part is modelled as a single field named `encrypted<Object>Object` (`encryptedFundingObject`, `encryptedDefundingObject`, `encryptedPaymentInstructionObject`, `encryptedPaymentObject`, `encryptedPaymentStatusObject`, `encryptedRefundObject`/`EncryptedRefundObject`). Its decrypted content is listed as a table, but no wire type is given.
- In POST /payments, POST /payments/{id}/status and the status-inquiry response, **the whole business payload is encrypted** ("The full payload is encrypted", p.68, p.79, p.110, p.113). Only `debtorAgent`, `creditorAgent` and `acceptanceDateTime` (p.65) or `debtorAgent`/`creditorAgent` (p.70) stay clear for routing.

**What DESP can read (cleartext)**, per the field tables:
- BICs of all agents (`instructingAgent`, `instructedAgent`, `debtorAgent`, `creditorAgent`)
- `amount`
- `paymentType`
- ledger entries (`userEntry`, `debtorEntry`, `creditorEntry`)
- UETR (except payee-initiated request messages)
- `acceptanceDateTime`
- statuses and IDs

**What DESP cannot read (encrypted, only when PSPs differ):**
- DEANs (`digitalEuroAccount`, `creditorAccount`, `debtorAccount`)
- IBAN (`commercialBankMoneyAccount`)
- names (`ownerName`, `accountOwnerName`, `creditor`, `debtor`, `ultimateCreditor`)
- remittance info, `purposeCode`
- end-to-end ID (`paymentIdentification` of type PaymentIdentification1)
- `transactionAmount`/`additionalAmount`/`totalAmount` breakdown
- `originalPaymentId`/`originalUetr`
- the whole request-for-payment content.

**Same-PSP case:** the encrypted part is *not sent at all*. It is mandatory only "in case digital euro payer and payee PSPs are different" or "in case of open (de)funding". So in a same-PSP payment DESP receives **no names, DEANs or remittance**, only entries, BICs and amount.

**Entry forwarding rule:** DESP strips the sender's entry before forwarding:
- "The user entry that was specified by the instructing PSP will not be forwarded to Instructed PSP." (p.94, p.99)
- "The payer entry that was specified by the payer PSP will not be forwarded to the payee PSP." (p.103)
- the same for refunds (p.115).

### 1.7 Error / reason codes
- Business rejection: status `RJCT` + `statusReason` (type `statusReason`, "C, mandatory in case of negative (business) validation"). [DD] Status reason = `statusReasonCode` (ExternalStatusReasonCode1, mandatory) + `statusReasonAdditionalInformation` (Max140Text, optional). **No concrete codes are listed in the settlement doc or the dictionary**, only "ExternalStatusReasonCode1" (the ISO 20022 external code list).
- Annex A instead uses two flat fields: "Status reason code" (SSET, 4) and "Additional information status reason" (STR, Max 100*70).
- Technical errors: not defined here (HTTP 4xx, see the Introduction document).

---

## 2. Endpoint catalogue

Legend:
- Presence: **M** = mandatory, **O** = optional, **C** = conditional (condition quoted).
- Types are exactly as printed (case and typos kept).
- `PaymentIdentification2` = `{ UETR: UUID(v7) }` [DD].
- `PaymentIdentification1` = `{ endToEndId: Max35Text }` [DD].
- `Financial institution Identification1` = `{ bicfi: BICFI (BIC11) }` [DD].
- `Amount` = `{ currency, amount: String }` [DD].
- `Entry` = `{ Entry ID: Tbd }` [DD].
- `Account reference` = `{ DEAN | IBAN }` (mutually exclusive) [DD].
- `Account owner` = `{ accountOwner: Max140Text }` [DD].
- `PartyDescription1` = `{ name }` [DD].
- `PartyDescription` = `{ name, postalAddress, identification, additionalPartyInformation }` [DD].
- `Remittance` = `{ reference, referenceType, referenceIssuer }` [DD].

### 2.0 Overview tables (p.46–49)

**DESP API (PSP → DESP), p.46–48**
| # | Method + path | Sender | Exposing party | Purpose |
|---|---|---|---|---|
| 1 | POST /fundings | Digital euro PSP | CBM PSP (via DESP) or DESP* | Funding request / complete funding data |
| 2 | POST /defundings | Digital euro PSP | CBM PSP (via DESP) or DESP* | Defunding |
| 3 | POST /payment-instructions | Digital euro payer PSP | Payee PSP (via DESP) or DESP* | Start settlement of a payment |
| 4 | POST /payments | Digital euro payee PSP | Payer PSP (via DESP) | Request for payment |
| 5 | POST /payments/{payment-id}/status | Payer PSP | Payee PSP (via DESP) | Async status of a request for payment |
| 6 | POST /refunds | Original payee's PSP (refund payer) | Original payer's PSP (via DESP) | Refund instruction |
| 7 | GET /fundings/{funding-id}/status | dEuro PSP or CBM PSP | DESP | Funding status |
| 8 | GET /defundings/{defunding-id}/status | dEuro PSP or CBM PSP | DESP | Defunding status |
| 9 | GET /payment-instructions/{payment-instruction-id}/status | Payer or payee PSP | DESP | Payment status |
| 10 | POST /payments/{payment-id}/status-inquiries | Payee PSP | Payer PSP (via DESP) | Query status of a request for payment |
| 11 | GET /refunds/{refund-id}/status | Payer or payee PSP | DESP | Refund status |
| 12 | GET /reports/transactions | PSP | DESP | Retrieve transactions report |
| 13 | GET /queries/enduser-entries | PSP | DESP | User entry(-ies) query |
| 14 | GET /reports/available-reports/?report-type=<report-type> | PSP | DESP | Available reports list |

**PSP API (DESP → PSP), p.48–49** (numbering continues at 14 in the spec)
| # | Method + path | Receiver | Purpose |
|---|---|---|---|
| 14 | POST /fundings | CBM PSP | Forwarded funding request (open funding only) |
| 15 | POST /fundings/{funding-id}/status | CBM PSP or dEuro PSP | Funding status |
| 16 | POST /defundings | CBM PSP | Forwarded defunding request (open defunding only) |
| 17 | POST /defundings/{defunding-id}/status | CBM PSP or dEuro PSP | Defunding status |
| 18 | POST /payment-instructions | Payee PSP | Forwarded payment instruction |
| 19 | POST /payment-instructions/{payment-instruction-id}/status | Payer and payee PSP | Payment status |
| 20 | POST /payments | Payer PSP | Forwarded request for payment |
| 21 | POST /payments/{payment-id}/status | Payee PSP | Forwarded async status of request for payment |
| 22 | POST /payments/{payment-id}/status-inquiries | Payer PSP | Forwarded status inquiry |
| 23 | POST /refunds | Payee PSP (of refund) | Forwarded refund |
| 24 | POST /refunds/{refund-id}/status | Payer and payee PSP | Refund status |
| 25 | POST /notifications/report-notifications | PSP | Report ready |

**Count:**
- DESP must expose **14** main-body endpoints (+3 reservation, informative).
- Every PSP must expose **12** main-body PSP-API endpoints to be able to play every role (+5 reservation as distributing PSP, +1 as acquiring PSP, informative).

---

### 2.1 DESP API (called by PSPs)

#### D1. POST /v1/fundings (p.49–53)
Sender: user's digital euro PSP → DESP. "Endpoint for funding transaction initiation." Also used for open funding (DESP forwards to the CBM PSP).

Request root:
| Field | Type | P | Meaning |
|---|---|---|---|
| acceptanceDateTime | ISODateTime | M | Determines max processing time; set by first PSP, unaltered |
| paymentIdentification | Payment identification2 | M | UETR |
| fundingObject | – | M | see below |

`fundingObject` unencrypted part:
| Field | Type | P | Meaning |
|---|---|---|---|
| instructingAgent | Financial institution Identification1 | M | User's digital euro PSP (BIC) |
| instructedAgent | Financial institution Identification1 | M | User's CBM PSP (BIC); "If the digital euro PSP is the same as the commercial bank money PSP, then the same value as instructing PSP must be filled in." |
| amount | Amount | M | Amount to be issued in digital euro holding |
| userEntry | Entry | M | User's digital euro holding in the settlement ledger |
| paymentType | PaymentType | M | Type of the payment |
| encryptedFundingObject | – | C, mandatory in case of open funding | see below |

`encryptedFundingObject` content (p.51–52), "required for open funding case":
| Field | Type | P | Meaning |
|---|---|---|---|
| digitalEuroAccount | Account reference | M | User's digital euro payment account (DEAN) |
| ownerName | Account owner | M | Name of the owner |
| remittanceInformationUnstructured | Max140Text | O | Free text; "mandatory ... if the user provides the remittance" |
| remittanceInformationStructured | Remittance | O | Structured remittance |
| commercialBankMoneyAccount | Account reference | M | User's non-digital-euro account (IBAN) |
| accountOwnerName | Account owner | M | Owner of non-digital-euro account |
| paymentIdentification | paymentIdentification1 | M | End-to-end ID from user; "NOTPROVIDED" if none |

Response 201 (p.52–53):
| Field | Type | P |
|---|---|---|
| paymentIdentification | Payment Identification2 | M |
| fundingId | UUID | M – "Resource ID generated by DESP" |
| fundingTransactionStatus | TransactionStatus | M – RJCT / ACTC / ACCP |
| statusReason | statusReason | C, negative business validation |

#### D2. POST /v1/defundings (p.53–57)
Mirror of D1. Root: `acceptanceDateTime` (M), `paymentIdentification` (Payment Identification2, M), `defundingObject` (Defunding object, M).

`defundingObject` unencrypted: `instructingAgent` (M, dEuro PSP BIC), `instructedAgent` (M, CBM PSP BIC; same value if same PSP), `amount` (Amount, M, "amount to be redeemed"), `userEntry` (Entry, M), `paymentType` (PaymentType, M), `encryptedDefundingObject` (C, mandatory in case of open defunding).

`encryptedDefundingObject` content (p.55–56): `digitalEuroAccount` (Account reference, M, "Unique identification of the UETR's digital euro payment account" [sic]), `ownerName` (Account owner, M), `remittanceInformationUnstructured` (Max140Text, O), `remittanceInformationStructured` (Remittance, O), `commercialBankMoneyAccount` (Account reference, M), `accountOwnerName` (Account owner, M), `paymentIdentification` (paymentIdentification1, M, "NOTPROVIDED" default).

Response 201: `paymentIdentification` (M), `defundingId` (UUID, M), `defundingTransactionStatus` (TransactionStatus, M; RJCT / "-" [blank] / ACTC / ACCP), `statusReason` (C, in case of failure).

#### D3. POST /v1/payment-instructions (p.57–64)
Sender: digital euro payer PSP → DESP. "Endpoint for a payer PSP to submit a payment instruction to start the settlement process of a payment transaction." Used for payer-initiated payments and, after a request for payment, also for payee-initiated ones. Can carry funding (reverse waterfall) and defunding (waterfall, same-PSP only).

Root:
| Field | Type | P | Meaning |
|---|---|---|---|
| acceptanceDateTime | ISODateTime | M | |
| paymentIdentification | Payment Identification2 | M | UETR |
| paymentInstructionObject | – | M | |
| fundingObject | – | O | "mandatory to be included if funding is needed" |
| defundingObject | – | O | "mandatory ... if defunding is needed and when payer and payee have the same digital euro PSP" |

`paymentInstructionObject` unencrypted:
| Field | Type | P | Meaning |
|---|---|---|---|
| debtorAgent | Financial institution Identification1 | M | Payer's PSP (BIC) |
| creditorAgent | Financial institution Identification1 | M | Payee's PSP (BIC) |
| paymentType | PaymentType | M | |
| amount | Amount | M | Total; must equal total in encrypted part if additionalAmount used |
| debtorEntry | Entry | M | Payer's holding in the ledger |
| creditorEntry | Entry | C, mandatory if payer and payee digital euro PSPs are the same | Payee's holding |
| encryptedPaymentInstructionObject | – | C, mandatory if digital euro payer and payee PSPs are different | |

`encryptedPaymentInstructionObject` content (p.59–61), "only required if payer and payee have different digital euro PSPs":
| Field | Type | P | Meaning |
|---|---|---|---|
| creditorAccount | Account Reference | M | Payee DEAN |
| creditor | PartyDescription1 | *(blank in spec)* | Name of payee |
| ultimateCreditor | PartyDescription | O | Payee party details |
| debtorAccount | Account Reference | M | Payer DEAN |
| debtor | PartyDescription1 | M | Name of payer |
| remittanceInformationUnstructured | Max140Text | O | |
| remittanceInformationStructured | Remittance | O | |
| purposeCode | Purpose code | O | ISO ExternalPurpose1Code [DD] |
| paymentIdentification | PaymentIdentification1 | O | Described as "Resource ID generated by the payee PSP to identify a payment request" [sic] |
| transactionAmount | Amount | M | |
| additionalAmount | Amount | O | Cashback or tip |
| totalAmount | Amount | C, mandatory if additionalAmount present | |
| originalPaymentId | UUID | C, mandatory if payee-initiated payment | `paymentId` from POST /payments |
| originalUetr | UUID | C, mandatory if payee-initiated payment | UETR of the original request for payment |

`fundingObject` (in payment-instructions) unencrypted (p.61):
| Field | Type | P | Meaning |
|---|---|---|---|
| instructedAgent | Financial institution Identification1 | M | Payer's CBM PSP; same as payer PSP if identical |
| amount | Amount | M | Amount to be issued |
| encryptedFundingObject | – | C, mandatory in case of open funding | Same as D1 encrypted part |

`defundingObject` (in payment-instructions) unencrypted (p.61–62), "required only when defunding is required and when payer and payee have the same digital euro PSP":
| Field | Type | P | Meaning |
|---|---|---|---|
| instructedAgent | Financial institution Identification1 | M | Payee's CBM PSP |
| amount | *(type blank)* | M | Amount to be defunded |
| encryptedDefundingObject | – | C, mandatory in case of open defunding | Same as D2 encrypted part |

(No `userEntry`, `instructingAgent` or `paymentType` inside these nested (de)funding objects. **[our inference]** DESP uses `debtorEntry` for funding and `creditorEntry` for defunding.)

Response 201 (p.62–64):
| Field | Type | P |
|---|---|---|
| paymentIdentification | paymentIdentification2 | M |
| paymentInstructionId | UUID | M – "Resource ID generated by DESP" |
| paymentTransactionStatus | TransactionStatus | M – RJCT / ACTC |
| fundingId | UUID | C, if funding object present and validation positive |
| fundingStatus | TransactionStatus | C, if funding object present – RJCT / ACTC |
| defundingId | UUID | C, if defunding object present and positive |
| defundingStatus | TransactionStatus | C, if defunding object present – RJCT / ACTC |
| statusReason | statusReason | C, in case of failure |

#### D4. POST /v1/payments (p.64–69)
Sender: payee PSP → DESP (forwarded to the payer PSP). "Endpoint for the payee PSP to send a request for payment." Note p.65: "the data elements in this endpoint will be further elaborated."

Root:
| Field | Type | P |
|---|---|---|
| acceptanceDateTime | ISODateTime | M |
| debtorAgent | FinancialInstutionIdentification1 | M – payer's PSP |
| creditorAgent | FinancialInstutionIdentification1 | M – payee's PSP |
| encryptedPaymentObject | – | M |

`encryptedPaymentObject` content:
| Field | Type | P | Meaning |
|---|---|---|---|
| paymentIdentification | PaymentIdentification2 | M | UETR (hence UETR encrypted, fn 12) |
| paymentId | UUID | M | "Resource ID generated by the payee PSP to identify a payment request" |
| expiryDateTime | ISODateTime | M | When the request expires |
| transactionAmount | Amount | M | |
| additionalAmount | Amount | O | Cashback or tip |
| totalAmount | Amount | C, mandatory if additionalAmount present | |
| creditorAccount | Account Reference | M | Payee DEAN |
| creditor | PartyDescription | M | Payee info |
| ultimateCreditor | partyDescription | O | |
| debtorAccount | AccountReference | M | Payer DEAN |
| debtor | PartyDescription | M | Payer info |
| remittanceInformationUnstructured | Max140Text | O | |
| remittanceInformationStructured | Remittance | O | |
| purposeCode | Purpose Code | O | |
| paymentIdentification1 | PaymentIdentification1 | M | End-to-end ID; "NOTPROVIDED" default |

Response 201 (p.68–69): "The full payload is encrypted. The payload is the same as in PSP API POST /payments", i.e. the payer PSP's answer relayed. Fields: `paymentIdentification` (PaymentIdentification2, M), `paymentStatus` (TransactionStatus, M; RJCT / ACTC), `statusReason` (C).

#### D5. POST /payments/{payment-id}/status (p.69–71)
Sender: payer PSP → DESP (forwarded to the payee PSP). "Endpoint for the payer PSP to asynchronously confirm status of a payment request." Used for **asynchronous rejection only** (allowed value RJCT). (The endpoint table prints the path as `/v1/payments/{payment-id}/status-inquiries` [sic].)
- Path: `paymentId` (UUID, M) – payee-generated ID.
- Root: `debtorAgent` (M), `creditorAgent` (M), `encryptedPaymentStatusObject` (M).
- Encrypted content: `paymentIdentification` (paymentIdentification2, M), `paymentStatus` (StatusCode, M; RJCT), `statusReason` (C).
- Response: 204, no body.

#### D6. GET /payment-instructions/{payment-instruction-id}/status (p.71–73)
Sender: payer or payee PSP. Purpose: query the status of a payment transaction. (The endpoint table again prints `/v1/payments/{payment-id}/status-inquiries` [sic].)
- Path: `payment-instruction-Id` (UUID, M).
- Response 200:

| Field | Type | P |
|---|---|---|
| paymentIdentification | Payment Identification2 | M |
| settlementDateTime | ISODateTime | C, positive result |
| settlementBusinessDay | ISODate | C, positive and funding/defunding object included – "Business day of the settlement which was recorded in dedicated cash account (DCA) in DESP" |
| paymentTransactionStatus | TransactionStatus | M – RJCT / ACSC |
| fundingStatus | TransactionStatus | C, if funding object – RJCT / ACSC |
| fundingId | UUID | C |
| defundingStatus | TransactionStatus | C – RJCT / ACSC |
| defundingId | UUID | C |
| statusReason | statusReason | C |

#### D7. GET /v1/fundings/{funding-id}/status (p.74–75)
"for commercial bank money payer or payee PSP to query the status of a funding transaction" (the overview table says dEuro PSP **or** CBM PSP).
- Path: `funding-id` (UUID, M).
- Response 200: `paymentIdentification` (M), `fundingTransactionStatus` (TransactionStatus, M; RJCT / ACSC), `statusReason` (C), `settlementDateTime` (ISODateTime, C positive), `settlementBusinessDay` (ISODate, C positive; recorded in DCA).

#### D8. GET /v1/defundings/{defunding-id}/status (p.76–77)
- Path: `defunding-id` (UUID, M).
- Response 200: `paymentIdentification` (M), `defundingTransactionStatus` (M; RJCT / ACSC), `statusReason` (C), `settlementDateTime` (C), `settlementBusinessDay` (C).

#### D9. POST /payments/{payment-id}/status-inquiries (p.77–79)
Sender: payee PSP → DESP (forwarded to the payer PSP). "Endpoint for the payee PSP to query status of a payment request with the payer PSP." (Table method says **GET**, heading says **POST**; see §6.)
- Path: `payment-id` (UUID, M).
- Body: `debtorAgent` (FinancialInstutionIdentification1, M).
- Response 200, "The full payload is encrypted": `paymentIdentification` (paymentIdentification2, M), `paymentStatus` (StatusCode, M; RJCT / "- -ACSC"), `statusReason` (C).

#### D10. POST /v1/refunds (p.79–85)
Sender: refund payer PSP (= original payee/merchant PSP) → DESP. "Endpoint to initiate a refund transaction."

Root:
| Field | Type | P |
|---|---|---|
| acceptanceDateTime | ISODateTime | M |
| paymentIdentification | PaymentIdentification2 | M |
| refundObject | – | M |
| fundingObject | – | O, "mandatory ... if funding is needed" |
| DefundingObject [sic, capital D] | – | O, "mandatory ... if defunding is needed" (no table given) |

`refundObject` unencrypted:
| Field | Type | P | Meaning |
|---|---|---|---|
| debtorAgent | Financial institution Identification1 | M | Refund payer's PSP (original payee PSP) |
| creditorAgent | Financial institution Identification1 | M | Refund payee's PSP (original payer PSP) |
| paymentType | PaymentType | M | |
| amount | Amount | M | Full or partial amount |
| debtorEntry | Entry | M | Refund payer's holding |
| creditorEntry | Entry | O ("must be included if payer and payee have the same digital euro PSP") | |
| encryptedRefundObject | – | C, mandatory if PSPs differ | |

`encryptedRefundObject` content (p.81–83):
| Field | Type | P |
|---|---|---|
| creditorAccount | Account Reference | M – original payer's DEAN |
| creditor | PartyDescription1 | M – original payer |
| debtorAccount | Account Reference | M – original payee's DEAN |
| debtor | PartyDescription1 | M |
| remittanceInformationUnstructured | Max140Text | O |
| remittanceInformationStructured | Remittance | O |
| purposeCode | Purpose Code | O |
| paymentIdentification | PaymentIdentification1 | M – "NOTPROVIDED" default |
| originalPaymentInstructionId | UUID | M |
| originalUetr | PaymentIdentification2 | M |

`fundingObject`: unencrypted "Same as ... POST /payment-instructions" (`instructedAgent`, `amount`, `encryptedFundingObject`). Encrypted part "Same as ... POST /fundings".

Response 201 (p.83–85):
| Field | Type | P |
|---|---|---|
| paymentIdentification | PaymentIdentification1 [sic] | M |
| refundId | UUID | M |
| refundTransactionStatus | TransactionStatus | M – RJCT / ACTC |
| fundingId | UUID | C |
| fundingStatus | TransactionStatus | C – RJCT / ACTC |
| defundingId | UUID | C |
| defundingStatus | TransactionStatus | C – RJCT / ACSC [sic] |
| statusReason | statusReason | C |

#### D11. GET /v1/refunds/{refund-id}/status (p.85–87)
- Path: `refund-id` (UUID, M).
- Response 200: `paymentIdentification` (M), `settlementDateTime` (C), `refundTransactionStatus` (M; RJCT / ACSC), `fundingStatus` (C; RJCT / ACSC), `fundingId` (C), `defundingStatus` (C), `defundingId` (C), `statusReason` (C).
- There is no `settlementBusinessDay` here, unlike the other status responses.

#### D12. GET /queries/enduser-entries (p.87–88)
Table path: `/v1/queries/end-user-entries ?entryId=<entryId>`. Resource "QUERIES", "User entry(ies) query".
- Query: `entryId` (Entry, "C, either entry identifier or Digital euro PSP identifier to be filled"). No PSP-identifier parameter is defined.
- Response 200:

| Field | Type | P |
|---|---|---|
| dateTime | ISODateTime | M – generation timestamp |
| digitalEuroAgent | financialInstitutionIdentification1 | M – BIC of dEuro PSP managing the entries |
| entryId | Entry | M |
| availableAmount | Amount | M |
| reservedAmount | Amount | M |
| totalAmount | Amount | M – available + reserved |

[DX] says the query supports selection by "entry(-ies) identifier" or "digital euro PSP identifier (BIC)", and returns per entry "digital euro PSP identifier (BIC), amount (available balance and sum of reservations), currency, timestamp".

#### D13. GET /reports/transactions (p.88–90)
Table path: `/v1/reports/transactions/?reportId=<reportId>`.
- Query: `reportId` (uuid, M) – from notification or available-reports.
- Response 200:

| Field | Type | P |
|---|---|---|
| reportedDate | ISODate | M |
| currency | Currency Code | M |
| digitalEuroAgent | financialInstitutionIdentification1 | M |
| reportStartDateTime | ISODatetime | M |
| reportEndDateTime | ISODatetime | M |
| *repeating per transaction:* | | |
| originatingDigitalEuroAgent | financialInstitutionIdentification1 | M |
| amount | Amount | M |
| paymenInstructiontId [sic] | UUID | M |
| paymentType | PaymentType | M |
| settlementBusinessDay | IsoDate | C, successful settlement ("RTGS business day") |
| settlementDateTime | ISODateTime | C, successful settlement |

Report attributes (p.44): recipient digital euro PSP; mode "Full or Delta"; view "Detailed"; frequency "As per subscription". It contains period, currency, originating PSP BIC, amount, "transaction reference", settlement timestamp. Only successfully settled transactions.

#### D14. GET /available-reports (p.90–92)
Table path: `/v1/ reports/available-reports?report-type=<report-type>`; overview: `GET /reports/available-reports/?report-type=<report-type>`. Description "Endpoint for recipient to retrieve the statement of account turnover" [sic].
- Query: `reportType` (Report Type, O). Values listed: DEUR "Digital euro report", DETR "Digital euro transactions report", FECR "Fee calculation report", REDR "Repository data report".
- Response 200, array:

| Field | Type | P |
|---|---|---|
| reportType | Report Type | M – "TRRE; Transactions Report" |
| *repeating per report:* | | |
| reportId | uuid | M |
| reportMode | Report Mode | M – FULL / DELTA |
| reportRtgsDate | ISODate | O |
| reportCalenderDate [sic] | ISODate | O |
| reportStartDateTime | ISODateTime | C, delta mode only |
| reportEndDateTime | ISODateTime | C, delta mode only |

---

### 2.2 PSP API (called by DESP; every PSP exposes these)

#### P1. POST /v1/fundings (p.93–95)
DESP → **commercial bank money PSP**. "to receive and validate funding requests." Only in open funding. Can come from DESP API POST /fundings, /payment-instructions or /refunds.
- Root: `acceptanceDateTime` (M), `paymentIdentification` (paymentIdentification2, M), `fundingObject` (Funding Object, M).
- `fundingObject` unencrypted ("The user entry that was specified by the instructing PSP will not be forwarded to Instructed PSP"):

| Field | Type | P |
|---|---|---|
| fundingId | UUID | M – DESP-generated; also "the funding leg of a payment/reservation transaction" |
| instructingAgent | Financial institution Identification1 | M |
| InstructedAgent [sic] | Financial institution Identification1 | M |
| amount | Amount | M |
| paymentType | PaymentType | M |
| encryptedFundingObject | – | M – same as D1 encrypted part |

- Response 201: `paymentIdentification` (M), `fundingTransactionStatus` (M; RJCT / ACCP), `statusReason` (C). No other "complement settlement data" field is defined, although the sequence text says the CBM PSP returns "complement settlement data".

#### P2. POST /v1/fundings/{funding-id}/status (p.95–97)
DESP → CBM PSP and/or digital euro PSP. "Endpoints for DESP to provide status of a funding transaction."
- Path: `funding-id` (UUID, M).
- Body: `paymentIdentification` (M), `fundingTransactionStatus` (M; RJCT / ACSC), `statusReason` (C), `settlementDateTime` (ISODateTime, C successful), `settlementBusinessDay` (ISODate, C successful; DCA business day).
- Response: 204.

#### P3. POST /v1/defundings (p.97–100)
DESP → CBM PSP (open defunding). Can come from DESP API POST /payment-instructions, /refunds, or from the **response** to PSP API POST /payment-instructions or /refunds.
- Root: `acceptanceDateTime` (M), `paymentIdentification` (M), `defundingObject` (M).
- `defundingObject` unencrypted (entry not forwarded): `defundingId` (UUID, M), `instructingAgent` (M), `InstructedAgent` (M), `amount` (M), `paymentType` (M), `encryptedDefundingObject` (M; same as D2 encrypted).
- Response 201: `paymentIdentification` (M), `defundingTransactionStatus` (M; RJCT / ACCP), `statusReason` (C).

#### P4. POST /v1/defundings/{defunding-id}/status (p.100–102)
- Path: `defunding-id`.
- Body: `paymentIdentification` (M), `defundingTransactionStatus` (M; RJCT / ACSC), `statusReason` (C), `settlementDateTime` (C), `settlementBusinessDay` (C).
- Response: 204.

#### P5. POST /v1/payment-instructions (p.102–106)
DESP → **payee PSP**. Forwards the payer PSP's instruction.
- Root: `acceptanceDateTime` (M), `paymentIdentification` (M), `paymentInstructionObject` (M).
- Unencrypted part ("The payer entry ... will not be forwarded to the payee PSP"): `paymentInstructionId` (UUID, M), `debtorAgent` (M), `creditorAgent` (M), `paymentType` (M), `amount` (Amount, M), `encryptedPaymentInstructionObject` (M; same as D3 encrypted part).
- Response 201 (this is how the payee PSP contributes its data):

| Field | Type | P |
|---|---|---|
| paymentIdentification | PaymentIdentification2 | M |
| paymentTransactionStatus | TransactionStatus | M – RJCT / ACCP |
| statusReason | statusReason | C |
| paymentInstructionObject | – | C, positive – contains `creditorEntry` (Entry, M): "Unique identification of the user's digital euro holding in the ledger" |
| paymentDefundingObject | – | O, "mandatory ... if defunding is needed" |

`paymentDefundingObject`: unencrypted "Same as ‘Defunding object data elements – unencrypted part’ in DESP API POST /payment-instructions" (`instructedAgent`, `amount`, `encryptedDefundingObject`). Encrypted part "required for open defunding case when the digital euro payee PSP is different from the commercial bank money payee PSP"; same as D2 encrypted part.

#### P6. POST /v1/payment-instructions/{payment-instruction-id}/status (p.106–109)
DESP → payer and payee PSP.
- Path: `payment-instruction-id` (UUID, M).
- Body: `paymentIdentification` (M), `settlementDateTime` (C, positive), `settlementBusinessDay` (C, successful settlement), `paymentTransactionStatus` (M; RJCT / ACSC), `fundingStatus` (C), `fundingId` (C), `defundingStatus` (C), `defundingId` (C), `statusReason` (C).
- Response: 204.

#### P7. POST /v1/payments (p.109–110)
DESP → **payer PSP**: a request for payment.
- Request body: "Payload is the same as in ‘Request body data elements’ in DESP API POST /payments".
- Response 201, "The full payload must be encrypted": `paymentIdentification` (M), `paymentStatus` (TransactionStatus, M; RJCT / ACTC), `statusReason` (C).

#### P8. POST /payments/{payment-id}/status (p.111–112)
DESP → payee PSP. Forwards the payer PSP's asynchronous status. (Endpoint table prints `/v1/payments/{payment-id}/status-inquiries` [sic].)
- Path: `payment-id` (type "PaymentIdentification" here).
- Body: same as D5.
- Response: 204.

#### P9. POST /payments/{payment-id}/status-inquiries (p.112–114)
DESP → payer PSP (table says method GET).
- Path: `payment-id` (UUID, M).
- Body: `debtorAgent` (M).
- Response 200, "full payload is encrypted": `paymentIdentification` (M, "Includes UETR"), `paymentStatus` (StatusCode, M; **RJCT / RCVD / ACCP / ACSC**), `statusReason` (C).

#### P10. POST /v1/refunds (p.114–118)
DESP → refund payee PSP (original payer PSP).
- Root: `acceptanceDateTime` (M), `paymentIdentification` (M), `refundObject` (M).
- `refundObject` unencrypted (payer entry not forwarded): `refundId` (UUID, M), `debtorAgent` (M), `creditorAgent` (M), `paymentType` (M), `amount` (M), `EncryptedRefundObject` [sic] (M; same as D10 encrypted).
- Response 201:

| Field | Type | P |
|---|---|---|
| paymentIdentification | PaymentIdentification2 | M |
| refundTransactionStatus | TransactionStatus | M – RJCT / ACCP |
| statusReason | statusReason | C |
| refundObject | – | M – contains `creditorEntry` (Entry, O "must be included if payer and payee have the same digital euro PSP") |
| defundingObject | – | O – unencrypted "Same as ‘Defunding object data elements – encrypted part’ in DESP API POST /payment-instructions" [sic]; encrypted for open defunding |

#### P11. POST /v1/refunds/{refund-id}/status (p.118–120)
- Path: `refund-id`.
- Body: `paymentIdentification` (M), `settlementDateTime` (C), `settlementBusinessDay` (C), `refundTransactionStatus` (M; RJCT / ACSC), `fundingStatus` (**M** here; RJCT / ACSC), `fundingId` (C), `defundingStatus` (C), `defundingId` (C), `statusReason` (C).
- Response: 204.

#### P12. POST /v1/notifications/report-notifications (p.120–123)
DESP → PSP, "Report ready notification".

| Field | Type | P |
|---|---|---|
| Agent | finacialInstitutionIdentification1 [sic] | M – BIC of PSP |
| reportType | Report Type | M – "see the relevant reference data table" |
| reportId | uuid | M |
| reportMode | Report Mode | M – FULL / DELTA |
| reportRtgsDate | ISODate | O |
| reportCalenderDate | ISODate | O |
| reportStartDateTime | ISODateTime | C, delta only |
| reportEndDateTime | ISODateTime | C, delta only |

Response: 204.

---

### 2.3 Annex A – Reservations (INFORMATIVE, v0.90 carry-over, p.124–174)
Annex A uses the older v0.90 notation: human-readable field names with a Length column, types STR/SSET, BIC as STR(11), amount as STR 14.3 + separate Currency STR 3. Roles are called "Distributing PSP" (payer side, A.1.1) and "Acquiring PSP" (payee side, A.1.2).

**DESP API (A.1.1.2.2.1 / A.1.2.2.2.1):**
| Method + path | Sender | Purpose |
|---|---|---|
| POST /v1/reservation-instructions | payer PSP | Payer-initiated reservation (p.136–140) |
| POST https://{server_region}.ecb.europa.eu/v1/reservation-requests/{id}/confirmation | payer PSP | Asynchronous answer to a forwarded reservation request (p.140–144) |
| GET /v1/reservations/{id}/status | payer or payee PSP | Status query (p.144–146) |
| POST /v1/reservation-request [sic singular] | payee PSP | Payee-initiated reservation request (p.164–167) |
| PUT /v1/reservations/{id} | payee PSP | Modify amount/expiry; cancel = amount 0 (p.167–171) |

**PSP API (A.1.1.2.2.2 / A.1.2.2.2.2):**
| Method + path | Receiver | Purpose |
|---|---|---|
| POST /v1/reservation-requests | payer PSP | Forwarded reservation request; API-specific header "Call Back Server" (p.147–150) |
| POST /v1/reservation-instructions/{id}/status | payer + payee PSP | Status of reservation instruction (p.150–153) |
| POST /v1/reservation-requests/{id}/status | payer + payee PSP | Status of reservation request (p.153–156) |
| PUT /v1/reservation /{id} [sic] | payer PSP | Forwarded modification (p.156–159) |
| POST /v1/reservations /{id}/status | payer + payee PSP | Status after modification or expiry (p.159–162) |
| POST /v1/reservation-instructions | payee PSP | Forwarded reservation instruction (p.171–174) |

Field lists:
- **POST /reservation-instructions** request:
  - Root: "Acceptance timestamp" (ISODateTime 26, M), "UETR" (STR 36, M), "Reservation object" (M), "Funding object" (O, if funding needed).
  - Reservation object unencrypted: "Payer PSP ID" (STR 11, M), "Payee PSP ID" (STR 11, M), "Payment type" ("Placeholder field for fee calculation related data", SSET, tbd, tbd), "Amount" (STR 14.3, M), "Currency" (STR 3, M), "Payer entry" (STR tbd, M), "Payee entry" (STR tbd, O; must be included if same PSP), "Expiry date time" (ISODateTime 26, M).
  - Encrypted part: same as the payment encrypted part. Funding: same as payment-instructions.
  - Response 201: "UETR" (M), "Reservation ID" (STR 36, M), "Reservation transaction status" (SSET 4, M), "Funding ID" (C), "Funding status" (C), "Status reason code" (SSET 4, C), "Additional information status reason" (STR Max 100*70, O).
- **POST /reservation-requests/{id}/confirmation**:
  - Header: "Reservation ID" (STR 36, M).
  - Body: "UETR" (M), "Reservation transaction status" (M), "Status reason code" (C), "Additional information status reason" (O), "Reservation object" (C, positive; contains "Payer entry" STR tbd M), "Funding object" (O).
  - Response 201: header "Reservation ID"; body "UETR", "Reservation transaction status", "Status reason code", "Additional information status reason".
- **GET /reservations/{id}/status** response 200: "UETR" (M), "Settlement timestamp" (C), "Remaining reserved amount" (STR 14.3, C), "Remaining reserved amount currency" (STR 3, C), "Expiry date time" (C), "Reservation transaction status" (M), "Funding status" (C), "Funding ID" (C), "Status reason code" (C), "Additional information status reason" (O).
- **PSP API POST /reservation-requests**:
  - Header: "Call Back Server" (STR tbd, M) = `https://{server_region}.ecb.europa.eu/v1/reservation-requests/{id}/confirmation`.
  - Root: "Acceptance timestamp", "UETR", "Reservation object".
  - Reservation object (payee entry not forwarded): "Reservation ID" (M), "Payer PSP ID", "Payee PSP ID", "Payment type" (placeholder: "The discussion on fee is still open"), "Amount", "Currency", "Expiry date time".
  - Response 201: "UETR", "Reservation transaction status", "Status reason code", "Additional information status reason". This is only receipt; the real answer comes via /confirmation.
- **PSP API POST /reservation-instructions/{id}/status** and **/reservation-requests/{id}/status**: header "Reservation ID". Body "UETR" (M), "Settlement timestamp" (C), "Remaining reserved amount" (C), "Remaining reserved amount currency" (C), "Expiry date time" (C), "Reservation transaction status" (M), "Funding status" (C), "Funding ID" (C), "Status reason code" (C), "Additional information status reason" (O). Response 200 without body.
- **PSP API PUT /reservations/{id}**:
  - Header: "Reservation ID". Root: "Acceptance timestamp" (M), "UETR" (M), "Reservation object" (M; same as acquiring-side PUT).
  - Response 200: "UETR" (M), "Request status" (M), "Status reason code" (C), "Additional information status reason" (O), "Funding object" (O, if the new amount is higher and funding is needed).
- **PSP API POST /reservations/{id}/status**: body "UETR" (M), "Settlement timestamp" (C), "Reservation transaction status" (M), "Expiry date time" (C), "Reservation modification object" (C, after PUT). The modification object contains "Request status" (M), "Funding status" (C), "Funding ID" (C), "Remaining reserved amount" (C), "Remaining reserved amount currency" (C), "Status reason code" (C), "Additional information status reason" (O). Response 200 without body.
- **DESP API POST /reservation-request(s)** (acquiring):
  - Root: "Acceptance timestamp", "UETR", "Reservation object".
  - Unencrypted: "Payer PSP ID", "Payee PSP ID", "Payment type" (tbd), "Amount", "Currency", "Payee entry" (M), "Expiry date time".
  - Encrypted: "Same as ‘Payment object data elements – encrypted part’ in DESP API POST /payment-requests" [non-existent endpoint].
  - Response 201: "UETR", "Reservation ID", "Reservation transaction status", "Status reason code", "Additional information status reason".
- **DESP API PUT /reservations/{id}** (acquiring):
  - Header "Reservation ID". Root "Acceptance timestamp", "UETR", "Reservation object", "Funding object" (O; "can only be included when payer and payee have the same digital euro PSP").
  - Unencrypted: "Payer PSP ID", "Payee PSP ID", "Payment type", "Latest reserved amount" (M), "Latest reserved currency" (M), "New reserved amount" (M), "New reserved currency" (M), "Latest expiry date time" (M), "New expiry date time" (M).
  - Encrypted: "Unstructured remittance information" (STR 140, O), "Structured remittance information" (STR tbd, O).
  - Response 200: "UETR", "Request status", "Status reason code", "Additional information status reason".
- **PSP API POST /reservation-instructions** (to payee PSP):
  - Root: "Acceptance timestamp", "UETR", "Reservation object".
  - Unencrypted (payer entry not forwarded): "Reservation ID", "Payer PSP ID", "Payee PSP ID", "Payment type", "Amount", "Currency", "Expiry date time".
  - Response 201: "UETR", "Reservation transaction status", "Status reason code", "Additional information status reason", "Reservation object" (C positive; contains "Payee entry" M).

---

## 3. Sequence diagrams (all steps)

**Our simulation rule:** for each end user, CBM PSP = digital euro PSP. Therefore:
- **Open funding/defunding never occurs.** No `encryptedFundingObject`/`encryptedDefundingObject`, no PSP API POST /fundings or /defundings ever reaches a PSP, and `instructedAgent` = `instructingAgent` (own BIC).
- Variants marked **APPLIES** are ours; **N/A (open)** variants are still useful to show in the explainer as "what would happen otherwise".
- "Same PSP for payer and payee" (two users at the same bank) and "different PSPs" (users at different banks) **both apply**.

### 3.1 Funding (Figure 1, p.17–18) – **APPLIES**
Same dEuro and CBM PSP; "all necessary settlement data can be shared with DESP in one API call". Refs LM-1.1, LM-1.3.
1. dEuro PSP → DESP `POST /fundings` with complete settlement data.
2. DESP → PSP synchronous response (201) confirming receipt.
3. *(DESP settles)* DESP → PSP `POST /fundings/{funding-id}/status`.
4. PSP → DESP synchronous response (204).

### 3.2 Funding with open funding (Figure 2, p.19–20) – N/A (open)
Refs LM-1.2, LM-1.4.
1. dEuro PSP → DESP `POST /fundings`, partial data, CBM PSP identifier given.
2. DESP → dEuro PSP 201.
3. DESP → CBM PSP `POST /fundings` (PSP API).
4. CBM PSP → DESP response with validation result + complement settlement data.
5. DESP → dEuro PSP `POST /fundings/{funding-id}/status` (simultaneously with 7).
6. dEuro PSP → 204.
7. DESP → CBM PSP `POST /fundings/{funding-id}/status`.
8. CBM PSP → 204.

### 3.3 Defunding (Figure 3, p.21) – **APPLIES**
Refs LM-2.1, LM-2.3.
1. `POST /defundings`, complete data.
2. 201.
3. DESP → PSP `POST /defundings/{defunding-id}/status`.
4. 204.

### 3.4 Defunding with open defunding (Figure 4, p.22–23) – N/A (open)
Refs LM-2.2, LM-2.4. Identical to 3.2 with defundings: 1 `POST /defundings` (partial) → 2 201 → 3 DESP→CBM `POST /defundings` → 4 response → 5/7 status to both (simultaneous) → 6/8 204.

### 3.5 Payment, same dEuro PSP for payer and payee, no (de)funding (Figure 5, p.24) – **APPLIES**
1. PSP → DESP `POST /payment-instructions`, complete data (both entries).
2. 201.
3. DESP → PSP `POST /payment-instructions/{payment-instruction-id}/status`.
4. 204.

**Rejection by DESP (Figure 6, p.25)** – APPLIES:
1. `POST /payment-instructions`.
2. Synchronous response rejecting the request. "As the request fails at the technical validation step, the status cannot be queried" (fn 20: resubmit with a new UETR).

### 3.6 Payer-initiated payment, different dEuro PSPs, no (de)funding (Figure 7, p.26–27) – **APPLIES**
Examples (fn 21–22): QR code, payer-initiated alias or DEAN, pay-by-link, in-app, standing order, NFC P2P, PwCB with QR.
1. Payer PSP → DESP `POST /payment-instructions` (partial data: no creditorEntry, encrypted part).
2. DESP → payer PSP 201.
3. DESP → payee PSP `POST /payment-instructions` (PSP API).
4. Payee PSP → DESP response: validation result + complement data (`creditorEntry`).
5. DESP → payer PSP `POST /payment-instructions/{id}/status` (simultaneously with 7).
6. Payer PSP → 204.
7. DESP → payee PSP `POST /payment-instructions/{id}/status`.
8. Payee PSP → 204.

**Rejected by payee PSP (Figure 8, p.28–29)** – APPLIES:
1–3 as above.
4. Payee PSP rejects in its synchronous response.
5. DESP → payer PSP `POST /payment-instructions/{payment-instruction-id}/status`.
6. Payer PSP → 204.

### 3.7 Payee-initiated payment ("request for payment"), different PSPs (Figure 9, p.30–32) – **APPLIES**
Examples: e-commerce with alias or DEAN (TM-2.2), payee-initiated P2P alias/DEAN (TM-3.6, TM-3.12), NFC/chip at POS (TM-1.2, 1.3, 1.6), PwCB NFC.
1. Payee PSP → DESP `POST /payments` with encrypted payment data.
2. DESP → payer PSP `POST /payments` (PSP API).
3. Payer PSP performs technical validation and responds acceptance/rejection.
4. DESP → payee PSP: forwards the response. On rejection the flow stops here.
   - *(fn 28: other calls can happen between 3 and 5, e.g. cryptogram check for NFC, payer authorisation in the app.)*
5. Payer PSP → DESP `POST /payment-instructions` (partial data; includes `originalPaymentId`, `originalUetr` in encrypted part).
6. DESP → payer PSP 201.
7. DESP → payee PSP `POST /payment-instructions`.
8. Payee PSP → response with validation + complement data.
9. DESP → payer PSP status (simultaneously with 11).
10. Payer PSP → 204.
11. DESP → payee PSP status.
12. Payee PSP → 204.

**Asynchronous rejection by payer PSP (Figure 10, p.32–33)** – APPLIES (e.g. payer declines or "does not respond in time" in the app, fn 29). Steps 1–4 as in Fig. 9, then:
5. Payer PSP → DESP `POST /payments/{payment-id}/status` (RJCT).
6. DESP → payee PSP `POST /payments/{payment-id}/status`.
7. Payee PSP → 204.
8. DESP → payer PSP: forwards the response.

**Same-PSP payee-initiated:** no separate diagram in this doc. **[our inference]** The same PSP would call `POST /payments` with itself as both agents (DESP relays back to itself), or skip straight to `POST /payment-instructions` with complete data. The spec does not say which.

### 3.8 Payment + (de)funding, all roles same PSP (Figure 11, p.33–34) – **APPLIES**
Covers payer and payee at the same bank, with funding and/or defunding.
1. PSP → DESP `POST /payment-instructions` with (1) payment object complete and (2) funding and/or defunding object(s) complete.
2. 201.
3. DESP → PSP `POST /payment-instructions/{id}/status` (includes fundingStatus/defundingStatus, fundingId/defundingId).
4. 204.

There are no separate `/fundings/{id}/status` pushes in this figure.

### 3.9 Payment with open funding and defunding, same dEuro PSP for payer and payee (Figure 12, p.35–36) – N/A (open)
1. dEuro PSP → DESP `POST /payment-instructions` with (i) payment complete, (ii) funding partial, (iii) defunding partial.
2. 201.
3. DESP → CBM payer PSP `POST /fundings` (simultaneously with 5).
4. CBM payer PSP → response.
5. DESP → CBM payee PSP `POST /defundings`.
6. CBM payee PSP → response.
7. *(settlement)* DESP → dEuro PSP `POST /payment-instructions/{id}/status` (simultaneously with 9, 11).
8. 204.
9. DESP → CBM payer PSP `POST /fundings/{funding-id}/status`.
10. 204.
11. DESP → CBM payee PSP `POST /defundings/{defunding-id}/status`.
12. 204.

### 3.10 Payer-initiated, different dEuro PSPs, open funding and defunding (Figure 13, p.37–39) – N/A (open), ref TM-3.11
1. Payer PSP → DESP `POST /payment-instructions` with (i) payment partial, (ii) funding partial.
2. 201.
3. DESP → payee PSP `POST /payment-instructions` (simultaneously with 5).
4. Payee PSP → response: validation + remaining payment data + partial defunding data (`paymentDefundingObject`).
5. DESP → CBM payer PSP `POST /fundings`.
6. CBM payer PSP → response.
7. DESP → CBM payee PSP `POST /defundings` (built from 4).
8. CBM payee PSP → response.
9. DESP → payer PSP payment status (simultaneously with 11, 13, 15).
10. 204.
11. DESP → payee PSP payment status.
12. 204.
13. DESP → CBM payer PSP funding status.
14. 204.
15. DESP → CBM payee PSP defunding status.
16. 204.

**Our variant (different dEuro PSPs, NON-open funding/defunding)** – **APPLIES, but no diagram in the spec.** **[our inference]**, combining Fig. 7 with the field rules:
- In step 1 the payer PSP adds `fundingObject` {`instructedAgent` = own BIC, `amount`, no encrypted part}.
- In step 4 the payee PSP adds `paymentDefundingObject` {`instructedAgent` = own BIC, `amount`} if the payee would exceed its holding limit.
- Steps 5–8 disappear (exposing party DESP per the * rule, p.48).
- Funding/defunding outcome is carried inside the `/payment-instructions/{id}/status` pushes (fields fundingStatus/fundingId and defundingStatus/defundingId), as in Fig. 11.
- The spec does not say whether DESP additionally pushes `/fundings/{id}/status` to a dEuro PSP that is also the CBM PSP.

### 3.11 Payee-initiated, different dEuro PSPs, open funding and defunding (Figure 14, p.40–41) – N/A (open), ref TM-1.3
1. Payee PSP → DESP `POST /payments` (encrypted).
2. DESP → payer PSP `POST /payments`.
3. Payer PSP technical validation response.
4. DESP forwards the response (stop on reject).
5–20. "follows the same steps as in Figure 13 (steps 1-16)".

Our non-open variant: Fig. 9 + funding/defunding objects as in 3.10.

### 3.12 Refund for e/m-commerce (Figure 15, p.42) – **APPLIES (structure)**
Scenario: different dEuro PSPs, no defunding, merchant's CBM PSP = its dEuro PSP. Ref TM-7.2.
1. Refund payer PSP (merchant's PSP) → DESP `POST /refunds` with refund object + funding object (partial data).
2. 201.
3. DESP → refund payee PSP (original payer's PSP) `POST /refunds`.
4. Refund payee PSP → response: validation + complement data (`creditorEntry`, optional `defundingObject`).
5. DESP → refund payer PSP `POST /refunds/{refund-id}/status` (simultaneously with 7).
6. 204.
7. DESP → refund payee PSP `POST /refunds/{refund-id}/status`.
8. 204.

Funding: "A refund always requires funding if the original payee's funds are not sufficient" (p.13). Annex A (p.125): "as business users have a zero holding limit". For us the funding object has `instructedAgent` = own BIC (non-open). Same-PSP refund: no diagram; `creditorEntry` "must be included if payer and payee have the same digital euro PSP".

### 3.13 Status query for a request for payment (Figure 16, p.43) – **APPLIES**
"a query which can be sent by the payee PSP to the payer PSP".
1. Payee PSP → DESP (table: "GET / payments/{payment-id}/status"; diagram: `POST /payments/{payment-id}/status-inquiries`).
2. DESP → payer PSP `POST /payments/{payment-id}/status-inquiries`.
3. Payer PSP → DESP synchronous response with status.
4. DESP forwards the response (table says "to the payer PSP" [sic; should be payee]).

Other status queries are simple GETs to DESP: payment-instructions, fundings, defundings, refunds (`/…/{id}/status`).

### 3.14 Transaction report retrieval (Figure 17, p.45) – APPLIES (optional for the sim)
1. DESP → PSP `POST /notifications/report-notifications`.
2. PSP → 204.
3. *(Optional)* PSP → DESP `GET /reports/available-reports`.
4. *(Optional)* DESP returns the list.
5. PSP → DESP `GET /reports/transactions` (reportId).
6. DESP returns the report.

"Steps 3 and 4 are optional and shall be executed in case of missed or unprocessed notifications."

### 3.15 Timeouts and rejections – what exists
- Rejection diagrams: Fig. 6 (technical reject by DESP), Fig. 8 (business reject by payee PSP), Fig. 10 (async reject of a request for payment by payer PSP), and Fig. 9 step 4 (sync reject by payer PSP).
- **No timeout sequence diagram.** Timeout-related elements:
  - `acceptanceDateTime` "used for determination of maximum processing time". The maximum value is not given.
  - `expiryDateTime` of a request for payment (D4).
  - fn 29: the payer "does not respond in time" → async RJCT via `POST /payments/{payment-id}/status`.
  - Annex A: reservation "Expiry date time ... any remaining reserved amount is automatically released"; `POST /reservations/{id}/status` is also sent "after the expiry date of a reservation transaction" (p.159).
- Recovery: status GETs; available-reports for missed notifications; resubmit with a new UETR after a technical error (fn 20).

### 3.16 Reservations (Annex A, INFORMATIVE)
**A-Fig 1, payee-initiated reservation creation with open funding (p.130–132)**, payer and payee PSPs different:
1. Payee PSP → DESP `POST /reservation-requests` (partial).
2. 201.
3. DESP → payer PSP `POST /reservation-requests` (with Call Back Server header).
4. Payer PSP → synchronous receipt (may already reject on technical validation; fn 40: between 4 and 5 the PSP may decode an NFC surrogate or gather a risk score).
5. Payer PSP → DESP `POST /reservation-requests/{id}/confirmation`: validation result + remaining reservation data (Payer entry) + partial funding data.
6. DESP → 201.
7. DESP → CBM payer PSP `POST /fundings`.
8. CBM response.
9. DESP → payer PSP `POST /reservations/{id}/status` (simultaneously with 11).
10. 200.
11. DESP → payee PSP `POST /reservations/{id}/status`.
12. 200.
13. DESP → CBM payer PSP `POST /fundings/{id}/status`.
14. Response.

**A-Fig 2, reservation lifecycle management, open funding (p.132–134)**:
1. Payee PSP → DESP `PUT /reservations/{id}` (new amount and/or expiry; 0 = cancel).
2. Response.
3. DESP → payer PSP `PUT /reservations/{id}`.
4. Payer PSP → validation + settlement data (+ funding object if the amount increases).
5. DESP → CBM `POST /fundings`.
6. Response.
7. Status to payer PSP (with 9).
8. Response.
9. Status to payee PSP.
10. Response.
11. Funding status to CBM.
12. Response.

**Claiming a reservation (p.135):** "follows the same process as the settlement of a payee-initiated payment transaction". If the total exceeds the reserved amount, either payer- or payee-initiated depending on the instrument.

For our sim, any reservation would be non-open: the funding object carries the own BIC and there are no `POST /fundings` hops.

---

## 4. DCA / liquidity and ledger "entries"

### 4.1 What the doc says about DCA
- p.10: settlement verification = "checking that a certain amount can be transferred between online digital euro and/or dedicated cash account (DCA) holdings". Settlement recording = "irrevocably and unconditionally transferring a certain amount of digital euro and/or DCA holdings".
- Footnote 4 (p.10): "Entry is either a user entry, which represents the identifier of a digital euro holding in the settlement ledger, or a DCA entry, which represents the identifier of a digital euro dedicated cash account in the settlement ledger." So **user holdings and DCAs live in the same DESP settlement ledger**, both addressed as "entries".
- The `settlementBusinessDay` field (all funding/defunding/payment/refund status messages) is the "Business day of the settlement which was recorded in dedicated cash account (DCA) in DESP". In payment status it is mandatory only "in case funding or/and defunding object was/were included in the original request" (p.72–73). In the transactions report it is the "RTGS business day on which the payment instruction is settled" (p.90). This implies that **funding/defunding moves money between a DCA and the user entry at settlement time, atomically with the payment**.
- **No DCA identifier appears in any settlement message.** The funding/defunding objects identify the commercial-bank side only by the BIC `instructedAgent` (+ encrypted IBAN for the CBM PSP). **[our inference]** DESP derives which DCA to debit (funding) or credit (defunding) from the `instructedAgent` BIC (the CBM PSP) via static/reference data. The spec does not state this mapping.
- The commercial-bank account debit/credit itself (IBAN side) is the CBM PSP's own business. DESP only gets the CBM PSP's validation result (`ACCP`/`RJCT`). The doc defines no message for it.
- [RB] PAR.01(2)–(3): a scheme participant "needs to have direct or indirect access to a DESP DCA, i.e. being able to be debited/credited in a DESP DCA as part of a funding/defunding operation" but "is not required to own or to be able to directly instruct a DESP DCA". [DX] lists DCA holders as a separate actor ("DCA holder ID", per-PSP lists "belonging to the DCA holder"). So a DCA holder can serve several dEuro PSPs.
- Liquidity transfers, DCA balance, floor/ceiling: separate DCA documentation [DX], not here.
- For our sim: funding = DCA(of PSP/DCA holder) → userEntry, plus the PSP debits the giro account internally. Defunding = userEntry → DCA, plus the PSP credits the giro account. Waterfall/reverse waterfall = the same legs inside one atomic payment settlement. **[our inference, consistent with p.10, fn 4 and settlementBusinessDay]**

### 4.2 Entries vs DEAN
| | Entry (`userEntry`, `debtorEntry`, `creditorEntry`, `entryId`) | DEAN |
|---|---|---|
| Meaning | "Identification of the user's digital euro holding in the settlement ledger" (p.51) | "Unique identifier of a digital euro payment account" [DD] |
| Format | Type `Entry` = { `Entry ID`: **Tbd** } [DD]. Annex A: STR, length tbd. No pattern given | Max18Text [DD]; [DX] STR 18 |
| Where in messages | **Cleartext** parts (DESP needs it to settle) | Only inside `Account reference` in **encrypted** parts (`digitalEuroAccount`, `creditorAccount`, `debtorAccount`) |
| Who sees it | Sender PSP + DESP. Not forwarded to counterparties (p.94, p.99, p.103, p.115); each PSP supplies only its own customer's entry (payee PSP returns `creditorEntry` in its response) | Counterparty PSPs (end to end); not DESP (in different-PSP flows) |
| Query | `GET /queries/enduser-entries?entryId=` → available / reserved / total | – (account data query in [DX]) |

- **The settlement doc does not define how an entry relates to a DEAN** (1:1? who generates the entry? when?). It only says the ledger works with entries and the payment data carries DEANs. The creation of entries and DEANs is out of scope of this doc (see §0).
- Entry field names used: `userEntry` (fundings/defundings), `debtorEntry` + `creditorEntry` (payment-instructions, refunds), `creditorEntry` (in PSP API responses), `entryId` (query). Annex A v0.90: "Payer entry", "Payee entry"; JSON example `endUserEntry`, `payerEntry`.
- Pseudonymity [our inference from the cleartext/encrypted split]: DESP sees ledger movements between entries, amounts, BICs and timestamps, but in different-PSP flows not DEANs/names. In same-PSP flows DESP gets neither DEANs nor names at all.

---

## 5. Code values

### 5.1 Payment type
- Settlement doc: type `PaymentType`, "Type of the payment". **No values listed in the main body.** Annex A: "Placeholder field for fee calculation related data" (SSET, tbd); JSON example `"paymentType": "P2P"`.
- [DD] "Payment type – This code set can be considered exhaustive":

| Code | Description |
|---|---|
| BP01 | B2P payment |
| DF01 | Defunding |
| FU01 | Funding |
| PB01 | POI payment (POS / eCOM) |
| PP01 | P2P payment |

  [DD] also says: "For all codes used in JSON structures, not the abbreviation defined for XML encoding, but the name of the code is used as a value." That is ambiguous for these codes.

### 5.2 Status values used in this doc
[DD] StatusCode: ACCP (AcceptedCustomerProfile), ACSC (AcceptedSettlementCompleted…), ACTC (AcceptedTechnicalValidation), RCVD (Received), RJCT (Rejected).

| Message | Field | Allowed values |
|---|---|---|
| D1 POST /fundings resp. | fundingTransactionStatus | RJCT, ACTC, ACCP |
| D2 POST /defundings resp. | defundingTransactionStatus | RJCT, (blank), ACTC, ACCP |
| D3 POST /payment-instructions resp. | paymentTransactionStatus, fundingStatus, defundingStatus | RJCT, ACTC |
| D4 POST /payments resp. (= P7 resp.) | paymentStatus | RJCT, ACTC |
| D5/P8 POST /payments/{id}/status | paymentStatus (StatusCode) | RJCT |
| D6 GET payment-instructions status | payment/funding/defunding status | RJCT, ACSC |
| D7/D8 GET (de)fundings status | …TransactionStatus | RJCT, ACSC |
| D9 status-inquiries resp. (DESP side) | paymentStatus (StatusCode) | RJCT, "- -ACSC" |
| P9 status-inquiries resp. (PSP side) | paymentStatus (StatusCode) | RJCT, RCVD, ACCP, ACSC |
| D10 POST /refunds resp. | refundTransactionStatus, fundingStatus / defundingStatus | RJCT, ACTC / RJCT, ACTC / RJCT, ACSC |
| D11 GET refunds status | all | RJCT, ACSC |
| P1/P3 PSP API POST /(de)fundings resp. | …TransactionStatus | RJCT, ACCP |
| P5 PSP API POST /payment-instructions resp. | paymentTransactionStatus | RJCT, ACCP |
| P10 PSP API POST /refunds resp. | refundTransactionStatus | RJCT, ACCP |
| P2/P4/P6/P11 status pushes | all | RJCT, ACSC |
| Annex A | "Reservation transaction status", "Request status", "Funding status" | SSET(4), values not listed |

Reading of the lifecycle [our inference from the tables]:
- **DESP's sync response:** ACTC (technical validation OK), or ACCP for standalone fundings/defundings.
- **Counterparty PSP's sync response:** ACCP (customer profile checks OK).
- **Final status push:** ACSC (settled) or RJCT.
- **Request-for-payment answers:** ACTC (payer PSP accepted technically), RCVD/ACCP/ACSC in status-inquiry answers.

### 5.3 statusReason codes
- **None listed in this document.** Type `statusReason`. [DD] {`statusReasonCode`: ExternalStatusReasonCode1 (M), `statusReasonAdditionalInformation`: Max140Text (O)}. Status reason code list = "ExternalStatusReasonCode1" (ISO 20022 external code set; concrete codes not given).
- Annex A: "Status reason code" (SSET 4) + "Additional information status reason" (STR Max 100*70).
- For the sim we will have to pick codes ourselves (e.g. from the ISO ExternalStatusReason1Code list). Mark them as **sim-chosen, not spec**.

### 5.4 Report codes
- `reportType` in the GET /available-reports request: DEUR, DETR, FECR, REDR.
- In the response: TRRE.
- [DD] Report type: ADMR, DIRE, FECR, FRMA, REDR, RDMR, TRRE.
- `reportMode`: FULL / DELTA in this doc; [DD] says FULL / **DELT**.

---

## 6. Placeholders, TBDs and inconsistencies

**Missing / external**
1. Technical header, technical errors, encryption mechanism, idempotency: all in the "Introduction and exceptions management section" (not provided). GET /available-reports refers to "section 5.3.3.1" instead (p.91–92).
2. No statusReason code values (§5.3). No PaymentType values in the main body (only [DD]).
3. `Entry` format is "Tbd" [DD]; Annex A "STR tbd".
4. No onboarding, DEAN, alias or entry-creation messages (§0).
5. Maximum processing time (derived from `acceptanceDateTime`) is not quantified. No timeout diagrams.
6. Reservations: Annex A informative only, not reviewed for v0.91 (p.124). Payment type there is a placeholder: "The discussion on fee is still open" (p.148).
7. POST /payments payload: "the data elements in this endpoint will be further elaborated" (p.65).
8. Fee-calculation data: the settlement data definition includes "fee calculation related data" (fn 6, p.10), but no fee fields exist apart from `paymentType`.
9. PSP API POST /fundings and /defundings responses: the text says the CBM PSP returns "complement settlement data", but the response defines only `paymentIdentification`, status and `statusReason` (p.95, p.100).
10. Same-PSP payee-initiated payment, same-PSP refund, and different-PSP payment with **non-open** (de)funding have no diagrams. Our main variants must be derived (§3.7, §3.10).

**Path / method inconsistencies**
11. D5 `POST /payments/{payment-id}/status`: the endpoint table shows `/v1/payments/{payment-id}/status-inquiries` (p.69). Same for P8 (p.111).
12. D6 `GET /payment-instructions/{payment-instruction-id}/status`: the endpoint table shows `/v1/payments/{payment-id}/status-inquiries` (p.71).
13. D9 / P9 status-inquiries: the heading says POST, the endpoint table says **GET** (p.77, p.112). D9 has a request body (`debtorAgent`), which suggests POST.
14. Fig. 16 (p.43): step 1 cites "GET / payments/{payment-id}/status" (does not exist). Step 2 says "forwards the request in API call 2" (should be 1). Step 4 says "forwards the response ... to the payer PSP" (should be payee). Footnote 12 also names "GET /payments/{payment-id}/status".
15. User-entry query: heading `GET /queries/enduser-entries`, table `/v1/queries/end-user-entries ?entryId=<entryId>`, section titles `end-user-entries` (p.87–88). The PSP-BIC selection criterion is mentioned but has no parameter.
16. Available reports: TOC "GET /available-reports"; overview "GET /reports/available-reports/?report-type=<report-type>"; table "/v1/ reports/available-reports?report-type=<report-type>"; parameter named `reportType` vs query `report-type`. Description "statement of account turnover" (copy-paste). Request values (DEUR/DETR/FECR/REDR) differ from the response value (TRRE) and from [DD].
17. Transactions report path `/v1/reports/transactions/?reportId=` (trailing slash). Field `paymenInstructiontId` (typo). Report attributes list "transaction reference", but no UETR field exists.
18. Annex A: `/v1/reservation-request` (singular, p.164), `/v1/reservation /{id}` (p.156), `/v1/reservations /{id}/status` (spaces). A reference to the non-existent "POST /payment-requests" (p.166). Reservation encrypted part in PSP API refers to "POST /reservation-requests Acquiring PSP section".

**Sequence text errors**
19. Fig. 9 title "Payer-initiated payment transaction with original request stemming from the payee PSP" (it is the payee-initiated flow). Step 2 "forwards the request sent in API call 2" (should be 1). Step 7 "from API call 6" (should be 5) (p.30–31).
20. Fig. 14 refers to "section 12.1.3.1.2.3 payer-initiated payment transaction with open funding and defunding" and "Section 12.2.2.1.3.3". The intended reference is 12.1.3.1.3.3 / Figure 13 (p.39, p.41).
21. Fig. 15 (refund) says the funding object carries "partial settlement data" although the scenario states merchant CBM PSP = dEuro PSP (p.41–42).

**Field-level inconsistencies**
22. Funding and defunding objects nested in payment-instructions/refunds lack `userEntry`, `instructingAgent` and `paymentType` (present in standalone /fundings). The defunding `amount` has no type (p.62).
23. "Funding object data elements – encrypted part: Encrypted part is only required for open **defunding** case" in the funding context (p.61, p.83, p.142): copy-paste.
24. Defunding encrypted `digitalEuroAccount`: "Unique identification of the **UETR's** digital euro payment account" (p.55).
25. `defundingTransactionStatus` allowed values contain an empty "-" (p.57).
26. DESP API POST /refunds has a `DefundingObject` (capital D) in the root, but no table. PSP API refund response: "Defunding object data elements – **unencrypted** part: Same as ‘... **encrypted** part’" (p.117). Annex A confirmation: the same mix-up (p.142).
27. Refund response: `paymentIdentification` typed PaymentIdentification1 (p.83; elsewhere PaymentIdentification2). `fundingStatus` RJCT/ACTC but `defundingStatus` RJCT/ACSC (p.84).
28. `creditorEntry` presence: "C" in payment-instructions (p.59) but "O" with the same rule in refunds (p.81, p.117). `fundingStatus` is "M" in PSP API refund status (p.119) but "C" elsewhere.
29. Payment-instruction encrypted part: `creditor` has no presence indicator. `paymentIdentification` is described as "Resource ID generated by the payee PSP to identify a payment request" but typed PaymentIdentification1 (p.60). `originalUetr` is typed UUID here but PaymentIdentification2 in refunds.
30. POST /payments encrypted part uses both `paymentIdentification` (UETR) and a field literally named `paymentIdentification1` (end-to-end ID) (p.65–68).
31. Agent type spelled "FinancialInstutionIdentification1", "finacialInstitutionIdentification1", "Financial institution Identification1". Field `Agent` (capitalised) in report notification. `InstructedAgent` capitalised in P1/P3. `EncryptedRefundObject` capitalised in P10.
32. Type naming: status fields typed `TransactionStatus` (in [DD] a *complex* type {status, statusReason}), but used as a flat code next to a separate `statusReason`. Some status fields are typed `StatusCode` instead.
33. `reportMode` FULL/DELTA vs [DD] FULL/DELT. `reportCalenderDate` spelling.
34. Payload summary table (p.15–16): the defunding "Unencrypted" row has an empty element cell (table split across pages; confirmed in the PDF).
35. GET /fundings and /defundings description: "for commercial bank money payer or payee PSP" (p.74, p.76) vs overview "Digital euro PSP or commercial bank money PSP" (p.47).
36. Response codes: main body status pushes → 204. Annex A status pushes → "200, without response body".
37. Annex A JSON examples (p.128–129) use v0.90 names (`acceptanceTimestamp`, `uetr`, `instructingPSP`, `instructedPSP`, `endUserEntry`, `paymentObject`, `payerPSPId`, `payeePSPId`, `payerEntry`, `fundingData`/`encryptionKey`/`encryptedFundingData`, `paymentInstructionData`/`encryptedpaymentInstructionData`, `"paymentType": "P2P"`) that do not match v0.91 field names. They also contain a JSON syntax error (missing quote before `U2FsdGVk…`).
38. Annex A DESP API PUT /reservations: "Funding object ... can only be included when payer and payee have the same digital euro PSP" (p.168). In A-Fig 2 the funding object comes from the payer PSP's PUT response instead.
39. Annex A "Remaining reserved amount" is described as "The amount to be transferred from the payer to the payee" (copy-paste). "Settlement timestamp" typed "ISODate Time".
40. Date: Data-exchange spec cover says 02/07/**2025**; settlement and dictionary say 02/07/2026 (cosmetic).

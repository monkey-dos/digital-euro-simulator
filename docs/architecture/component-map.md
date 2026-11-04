# Digital Euro Simulator – Component Map (v0.2)

Based on: ECB digital euro scheme rulebook v0.91 (draft, July 2026); Annex D1 part 1 (Distributing PSP requirements) and part 7 (Data management); Annex D2 part 1 (Introduction and exceptions, read from the web), part 6 (Data exchange), part 7 (Settlement, read in full) and part 8 (Data dictionary).
Detailed reference notes: `spec-notes/settlement-catalogue.md`, `spec-notes/frontend-notes.md`.
Interactive version: artifact "Digital Euro Component Map".
All documents are drafts, "not intended as a basis for implementation". That is fine for a teaching simulation; no real money flows.

## Components

### Eurosystem / DESP (central infrastructure)
| Component | Phase | Job | Basis |
|---|---|---|---|
| Eurosystem Access Gateway | 1 | Named in the glossary (p.173) as passing settlement instructions on. Using it as the single entry point for all bank traffic is our simplification | partly spec |
| Access Management | 1 | Pseudonymous user registry, DEAN generation, DEAN→PSP mapping, alias registry. Simulation simplification: answers the bank's "existing account?" check (the rulebook gives that check to the bank) | spec |
| Alias Lookup | 1 | Phone number or DEAN → servicing PSP | spec |
| Settlement Engine | 1 | Accepts fundings, defundings, payment instructions, payments, refunds. Forwards them to the other bank, settles atomically and pushes the status to all banks involved | spec |
| Central Ledger | 1 | Balance per ledger entry, reservations, transaction journal. No names. Settlement works on entries; DEANs travel only encrypted between banks. DCAs are entries in the same ledger. The entry↔DEAN link is undefined in the spec; Access Management keeps it in the sim | spec |
| DCA Simulator (TARGET, entries in the DESP ledger) | 1 | Central bank money accounts; a bank needs direct or indirect access to one (PAR.01). Debited on funding, credited on defunding. Simplified: one DCA per PSP | spec (simplified) |
| Participant Register | 1 | List of participating PSPs, kept by the Scheme Governing Authority on the ECB website, not a DESP service (config file in phase 1) | spec |
| SEPI Token Service | 2 | QR / pay-by-link / NFC tokens | spec |
| Fraud Risk Scoring | 3 | Risk score per payment (mock) | spec |
| Dispute Management | 3 | Dispute status lifecycle, hashes only | spec |
| Data Exchange | 3 | Reports and queries PSPs pull (D2-6) | spec |

### PSPs (at least two, built independently)
- **PSP A – retail bank** (individuals). Back-end: customers and KYC, customer↔DEAN link, balance and reverse-waterfall check as payer bank, holding-limit and waterfall check as payee bank, payment initiation, DESP connector. It must also offer an **inbound interface**, because DESP calls the banks.
- **PSP B – bank + acquiring** (individuals and businesses). Same parts, plus merchant acquiring in phase 2.
- **Core banking** (one per PSP, simulation stand-in): giro accounts (bank money) used for funding, defunding, waterfall and reverse waterfall. **Decision:** a customer's giro account is always at the same bank as their digital euro access. Digital euro always sit on the ECB ledger; the bank only provides the interface. Defunding turns digital euro into bank money on the giro account.
- **More banks:** the PSP app is one template; PSP C etc. = another instance with its own configuration and a register entry.

### Users and front-ends
- Banking App A, Banking App B: separately built, both speak the same front-end interface (I1, messages per Annex D1-1), so they can be swapped (phase 1). Screens are our own design (screen spec D1-3 not available).
- Merchant Gateway and POS / Webshop (phase 2).

### Simulation layer (not in the spec)
- **Network Relay**: all traffic between apps passes through it. It delays each hop (slow motion) and copies messages to the observer, so the apps stay unchanged.
- **Transparency Observer**: **decision: everything is visible.** Live message flow, ledger and DCA balances, status steps, replay. Optional lenses: what DESP sees / what a PSP sees / public totals.
- **Game Master Console**: speed, pause, single-step, reset, test users, scenarios. **Decision (amended 4 Nov 2026, ADR 0002):** the game master may create **Helicopter Money** for people: new digital euro on a person's DEAN ledger entry, or new central bank money on a bank's DCA that the bank credits to the person's giro account (the bank books "DCA at the central bank +X / giro +X"). There is no stand-alone DCA top-up. That creates money, which is impossible in reality, so every drop is labelled and totalled separately. The relay orchestrates it through the gate; the DESP and the banks offer simulation-only `/sim/helicopter-money` endpoints.
- **Interface Contracts**: folder in the shared repository with API definitions and sample messages per interface.

## Interfaces
| # | Between | Basis | Phase |
|---|---|---|---|
| I1 | Banking app ↔ its PSP. Envelope: MessageIdentification, EventIdentification, CreationDateTime → ReturnCode, StatusReason. Payloads for registration, alias, balance, liquidity settings, funding/defunding, P2P, payment request, standing orders, history, offboarding | spec (D1-1) | 1 |
| I2 | Merchant system ↔ gateway ↔ acquiring PSP | partly spec | 2 |
| I3 | PSP ↔ DESP, both directions (REST/JSON). Bank→DESP 14 endpoints (POST /fundings, /defundings, /payment-instructions, /payments, /refunds, status, /queries/enduser-entries, reports). DESP→bank 12 endpoints, 10 needed in our setup (forwarded instructions, POST …/status answered with 204, report notifications). Pattern: 201 receipt, then status push. DESP reads bank codes, amount, payment type, entries, UETR, status; DEANs, names, IBANs, payment text are encrypted for the other bank | spec (D2-7, D2-1, D2-6) | 1 |
| I4 | DESP ↔ DCA (TARGET) | partly spec | 1 |
| I5 | PSP back-end ↔ its core banking | ours (bank-internal) | 1 |
| I6 | All apps → relay → observer | ours | 1 |
| I7 | Game master → all | ours | 1 |

## Key rules for the ledger
- DEAN (example EU9500000000004217, made up): 18 characters = "EU" + 2 check digits (MOD 97-10) + type digit (0 private, 1 business) + 13-digit serial, generated by DESP (FUR.69).
- One account per individual; the bank checks this and offers a switch instead (AM-011-003/004). Businesses may have many (AM-012).
- Alias: phone number, individuals only, one to one with the DEAN.
- Holding limit: amount not set in the rulebook; businesses have 0 (LM-012-001).
- Reverse waterfall = top up from the giro account when the balance is too low. Waterfall = sweep the excess above the limit to the giro account. Both are settled atomically with the payment.
- Status: RCVD → ACTC → ACCP → ACSC, or RJCT. In JSON the full code name is used (e.g. AcceptedSettlementCompletedDebitorAccount).
- Pseudonymous user ID: the rulebook leaves the format open; the data dictionary makes it a UUID v7 generated by the bank.
- Privacy: the ECB must not be able to tie the user ID to a person (rulebook p.42, 175). Payer and payee details travel encrypted between banks (settlement annex).
- Invariant for the observer: money in circulation = sum of all DEAN balances = opening balances + net DCA debits (DCA changes from Helicopter Money left out) + digital euro Helicopter Money. Cross-check per bank: the central bank money the DESP created on its DCA = the giro Helicopter Money the bank credited to customers.

## Phases
1. **Money between people**: open account, alias, funding/defunding, P2P at the same and the other bank, waterfall and reverse waterfall, observer with slow motion.
2. **Merchants**: business onboarding, QR in store, pay-by-link, refunds, pre-authorisation (binding in the rulebook, TM-050…052; message details in the settlement annex are only informative).
3. **Scheme depth**: fraud score, disputes, reports, switching, standing orders, offline.

## Decisions (agreed 1 Nov 2026)
1. Holding limit: adjustable by the game master, 3,000 € placeholder.
2. Everything visible; a game master can create Helicopter Money for people (money creation in two kinds, labelled and totalled separately; amended 4 Nov 2026, ADR 0002).
3. Giro accounts always at the same bank as the digital euro access; digital euro always on the ECB ledger, the bank only provides the interface.
4. PSP B serves merchants, PSP A only individuals; a third bank may follow (PSP app is a template).
5. One account per person, enforced (bank asks the central user registry; sim simplification).
6. Documents: D2-7, D1-1, D1-7 attached; D2-1 read from the web.

## Known gaps
- Onboarding (DEAN request, user/alias registration, deregistration): only referenced (GET /users/{userID}, PUT /deans); full spec in D1-5 / D2 access management, not available. The sim uses placeholder calls, marked as such.
- App screens and branding (D1-3) not available.
- No complete reason-code list (part 1 has AC05, AC06, AB03, D005).
- Entry format "to be defined"; no message names the DCA used for funding.
- Security and encryption method not specified.
- ~40 inconsistencies in D2-7, plus contradictions between the two D1 documents (e.g. the waterfall flag); each gets one documented choice.
- All documents are drafts; the ECB also mentions separate pilot documentation.

> Machine-generated reading notes for the digital euro simulator (Nov 2026). Always check names and fields against the original ECB document before relying on them.

# Front-end spec notes: Annex D1 #1 (Distributing PSP) and #7 (Data management)

Reference notes for the digital euro **simulation** (no real money). Source documents (both "Draft digital
euro scheme rulebook v0.91", dated 02/07/2026, status DRAFT, explicitly "not intended for use as a basis for
implementing any systems"):

- **[PSP]** Annex D1 Front-end implementation specification #1 "Distributing PSP requirements", 131 pages
- **[DATA]** Annex D1 Front-end implementation specification #7 "Data management", 65 pages
- Cross-checked (only where marked **[RB]**) against the main rulebook v0.91, and a few lines of Annex D2 #6
  Data exchange **[D2-6]**. These were not read in full.

Page refs are the PDF page numbers ("PAGE x OF n"). Names in quotes are copied exactly from the source,
typos included. "n.s." = not specified in these documents. **Anything marked "(inference)" is my reading, not
spec text.**

---

## 0. Key facts for the architecture

1. **Which spec covers which part.** [PSP] covers the distributing PSP's back office, meaning the functions a
   PSP runs when the app calls it. The **app itself** (screens, UX, branding) is covered by **Annex D1
   Specification #3** "Individual user domain". That document was **not provided** ([RB] pp.92-95; the
   figure on [PSP] p.83 is labelled "SPEC 3 Individual User domain"). **Common services** (DEAN
   registration, alias look-up, PSP ID look-up, tokenisation, (de)funding settlement, payment processing,
   fraud, notification/reason codes, user deactivation) are in **Specification #5 "Common services"**, also
   not provided. Spec #6 (technical standard) is "will be included in a future version" ([RB] p.97).
2. **PSP↔DESP messages are in Annex D2 (back-end).** [PSP] only points to them by name, for example
   `"GET/ users /{userID}"` and `"PUT/ deans – Response"` (see §2).
3. **Scope of [PSP] v0.91** (p.9): onboarding, lifecycle management and offboarding of an individual user;
   online manual funding/defunding (same PSP); P2P with alias (payer- and payee-initiated); P2P with DEAN
   (payer-initiated); P2P with QR code (payee-initiated); P2P with pay-by-link (payee-initiated; the section
   is only a placeholder, p.24); standing orders; P2B NFC payment (payee-initiated). **Offline is out of
   scope** (p.10). [DATA] also covers online only (p.6).
4. **One account per individual.** "assumes a single-account set-up for individual digital euro end-users"
   (Preamble p.3). "Each individual user is allowed to open only one digital euro payment account" (p.54).
   [RB] AM-011-001.
5. **The giro account is "non-digital euro payment account" (CBMA = "Commercial Bank Money Account").**
   Linking it is optional at onboarding (Fig.1, p.11). The link is "a pre-requisite to waterfall and reverse
   waterfall processes" (p.62). (De)funding covered here is only "same PSP" (pp.19-20). This matches the
   project assumption that the giro account sits at the same bank.
6. **Every function returns `ReturnCode` + `StatusReason`.** Reason codes are always deferred to
   "Specifications#5 – Cross functional service / Notification". **No reason-code list exists in these two
   documents.**
7. **Diagrams are not sequences.** Figures in §4 "are conceptual views … Their purpose is not to be sequence
   diagrams. The sequences are reflected in the end-to-end flows" (p.11). The E2E flows are in Annex B2,
   which was not provided.
8. **[RB] warning** (p.93 fn 38/39): access management and liquidity management specs "have not been
   aligned with the latest version of the E2E flows (Annex B2)".

---

## 1. What the distributing PSP must offer the front-end (banking app), per journey

### 1.0 Common message envelope (useful as the I1 base contract)

Every app→PSP **incoming message** in [PSP] carries:

| Data element | Type | Len | Pres. | Standardised name |
|---|---|---|---|---|
| Identifier of the message | STR | 35 | M | MessageIdentification |
| Identifier of the event (fixed string, e.g. "Alias registration") | STR | 35 | M | EventIdentification |
| Date of the message, `YYYY-MM-DDThh:hh:sssZ` | Datetime UTC | 24 | M | CreationDateTime |

Every **outgoing message** (PSP→app, or the result of an internal function) carries:

| Data element | Type | Len | Pres. | Standardised name |
|---|---|---|---|---|
| Identifier of the message | STR | 35 | M | MessageIdentification |
| Identifier of the incoming message | STR | 35 | O | OriginalMessageIdentification |
| Date of the message | Datetime UTC | 24 | M | CreationDateTime |
| Return code: `0` Successful / `1` Failure | BOOL | 1 | M | ReturnCode |
| Reason code ("Populated only in case of rejection") | NSET | 4 | O | StatusReason |

Notation (p.10): presence M/O/C. "Standardised name" is ISO 20022, and is "(New for digital euro)" where none
exists. Data types (p.10, also [DATA] p.42): STR, NUM, BOOL, SSET, NSET, Number range, Date `YYYY-MM-DD`,
UTC time `HHMMSSsss`, Datetime UTC `YYYY-MM-DDThh:hh:sssZ` (sic), BIN, UUID. Amounts are NUM 18 with a dot as
the decimal separator, and the number of decimals follows ISO 4217 ([DATA] p.52).

Pre-requisite repeated for most app-initiated functions: "The PSP app is already connected to the
distributing PSP through a Strong Customer Authentication process specific to that PSP" (e.g. pp.42, 47, 58,
70, 82). **Authentication service specs are deferred** ([RB] p.97).

### 1.1 Onboarding (Access management), Fig.1 p.11 and §6.2/§6.3

App steps shown in Fig.1: "App Opening", "Onboarding Request", "Authentication", "Alias Entry", "CBMA Link",
"Liquidity Settings", "Notification Settings". Alias, CBMA link and the two settings steps are drawn as
optional. PSP functions shown: New Digital Euro User Registration (Request Validation); New Digital Euro
Account Existence Check, same PSP and other PSP; New Digital Euro User Registration; Alias Registration
Service (Request Validation, Alias Ownership Check, Alias Registration for DEAN); Liquidity Settings Service
(Validation, Storage); Notification Settings Service (Validation, Storage); Authentication Service;
Digital Euro Account Service, "DEAN Registration"; Linked Account Settings Service (CBMA Link Request
Validation, CBMA Ownership Check, Linked CBMA Information Storage); Notification Service.

Functions:

- **KYC registration** (6.2.1.1, p.46) and **New customer registration** (6.2.1.2, p.46): the existing
  processes are used unchanged. The user "must be identified as the same PSP's customer".
- **New digital euro individual user registration request validation** (6.2.1.3, pp.47-48), event
  "Digital euro user registration". Rules: (1) M, the format is consistent; (2) M, "Account type (DEUR)" must
  be provided "And the PSP must directly trigger digital euro payment account creation and related steps";
  (3) M, return code. Incoming payload: **Type of the new account**, SSET 4, M, `CashAccountType`,
  "DEUR" (to be confirmed).
- **Digital euro payment account existence check – same PSP** (6.3.1.1, pp.54-55). An internal check,
  triggered by the PSP. An account "shall be deemed to exist only if its status is other than 'Closed'". If one
  exists, onboarding is discontinued. Output: **Indicator of already existing DEAN**, BOOL (0 none / 1
  found).
- **… existence check – other PSP** (6.3.1.2, p.55): "the distributing PSP must also check if the user is
  already registered in DESP" → **Annex D2 `"GET/ users/{userID} – Request" | "GET/ users/{userID} –
  Response"`**. "If the user is already registered in DESP, the user must be requested to perfom an account
  switching."
- **New digital euro individual user registration** (6.2.1.4, pp.48-50). The PSP creates the "digital euro
  user data envelop" containing: Digital euro user Identifier, Technical proof, Entry Identifier, Digital
  euro user type, creation date, status, country, language.
  - Rule 3 M: "link the Digital Euro User Identifier with the PSP App ID associated with the app that
    initiated the request".
  - Rules 4/5/6: the generation rules for user identifier, technical proof and entry identifier are
    **"(placeholder)"**.
  - Status starts as **PENDING** ("registered but has not yet opened a digital euro payment account").
  - Type is "Individual" (**INDI**).
  - Outgoing message adds: **Identifier of the digital euro user** (STR, TBD, O) and **Technical proof**
    ("Cryptographic root key used to prove the ownership of holdings", STR, TBD, O), both "Populated if the
    process is successful".
- **DEAN registration** (listed in 6.5, p.61): "The PSP requests a DEAN to DESP and stores it." Described in
  Spec #5.
- **Alias registration** (see 1.3), optional during onboarding.
- **CBMA link** (see 1.4), optional.
- **Liquidity and notification settings** (see 1.6 and 1.11), optional.
- [RB] AM-011-005 (p.49): the PSP "must request a DEAN and registration of the user in the DESP, including the
  mapping to itself as the corresponding PSP and including a potential alias". AM-011-006: "The PSP must share
  the DEAN and technical proof with the individual user when onboarding is completed successfully."
  → **The app must display or deliver the DEAN and the technical proof.**

### 1.2 DEAN display

- The DEAN is STR 18 ([DATA] p.56; [PSP] p.51 and others). The format and check rules are n.s. here. "DEAN
  Validity check: The PSP … checks if the DEAN provided is consistent" (Spec #5).
- NFC enrolment returns **"DEAN last four digits"**, STR 4, "to be print on the payment receipt" ([PSP]
  p.85; [DATA] p.55, flagged "visible to the end-user").
- The transaction history response contains the payee's DEAN, M ([PSP] p.128).

### 1.3 Alias (6.1, pp.42-45)

"A user may initiate a payment using an alias, as long as the alias is associated with their DEAN." The
service is triggered on create, update and remove.

- **Alias registration request validation** (6.1.1.1), event "Alias registration". Rules:
  1. M: format and content are consistent.
  2. M: type of request is CREATE / UPDATE / DELETE.
  3. M: alias type and value are present.
  4. M: the value is consistent with the type.
  5. M: CREATE only if the alias is not already registered.
  6. M: UPDATE/DELETE only if it is already registered.
  7. **M: "Each end user is allowed to register only one alias, even if they use multiple apps."**
  8. M: return code.

  Payload:
  - **Type of request**: SSET 4 M `RequestType`, values `CRED`/`UPDT`/`DELT`.
  - **Type of alias**: SSET 4 M `ProxyAccountType`, ISO ExternalProxyAccountType1code, `EMAL` (email) /
    `MBNO` (mobile).
  - **Value of alias**: STR 2048 M `ProxyAccount`. "MBNO alias shall be strict E.164 Format with leading +
    and no other characters".
- **Alias ownership proof validation** (6.1.1.2, pp.44-45). Internal, triggered after validation. "The current
  rules used by the distributing PSP to validate the ownership of a mobile phone number of an email address
  are reused." Output: **Alias ownership indicator**, BOOL M `Ownership` (1 validated / 0 not).
- **Alias registration for a DEAN** (6.1.1.3, p.45): "The DESP manages the link between an alias and a DEAN.
  For any action related to an alias … the distributing PSP must submit a registration request to the DESP."
  → Annex D2 `"GET/ users /{userID} – Request" | "GET/ users /{userID}– Response"` (quoted as written. A GET
  for a registration looks like a copy-paste of the 6.3.1.2 reference (inference)).
- [DATA] p.9 fn 2: "The number of aliases available at launch may be limited to one." [DATA] p.12: an alias
  "can only be attributable to an identifiable natural or legal person by the payment service provider
  distributing the digital euro or by the digital euro user".

### 1.4 Linking the giro account / CBMA (6.7, pp.62-63)

"An end-user who has successfully opened a digital euro payment account must have the ability to link a
non-digital euro payment account … for funding and defunding purposes." Functions (all Spec #5): Linked
account settings request validation; storage ("new link, updated link, link removal"); removal (at
offboarding); "Linked non-digital euro payment account ownership validation"; look-up; check (returns the
IBAN during (reverse) waterfall). **No message structure is given here.** [DATA] p.10: a digital euro
account is linked to "0 to one" non-digital euro account, and vice versa.

### 1.5 Manual funding / defunding (Fig.9/10 pp.19-20, §7.1 pp.96-99)

App steps (Fig.9): "App Opening", "Funding Option Selection", "Digital Euro Balance Request", "CBMA Entry or
Selection (if already registered)", "Amount Entry", "Message to the targeted CBMA owner", "Enter End to End
Identification", "Confirm", "Notification".

**Manual funding/defunding request initiation validation** (7.1.1.1). The same structure is used for both.

- Type of request: SSET 4 M, `ONLF` (Online funding request) / `ONLD` (Online defunding request).
- ONLF: event "Online funding request"; debited account type `CBMA`, credited `DEUR`; the debited CBMA is
  populated; transaction type **`FU01`**.
- ONLD: event "Online defunding request"; debited `DEUR`, credited `CBMA`; transaction type **`DF01`**.
- On success the PSP generates a **UETR**, "UUID type (xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx)", and stores the
  transaction.

Payload (pp.97-98):

| Field | Type | Pres. | Standardised name |
|---|---|---|---|
| Transaction type | SSET 4 | M | TransactionType |
| Digital euro account number | STR 18 | O | |
| Type of debited account (`CBMA`/`DEUR`) | SSET 4 | M | CashAccountType |
| Debited account identification | STR 34 | M | DebtorAccount |
| Debited Account PSP identification (BIC) | STR 11 | O, "mandatory only for funding to route the request in case of different PSPs" | DebtorAgent |
| Credited account identification | STR 34 | M | CreditorAccount |
| Type of credited account | SSET 4 | M | CashAccountType |
| Credited Account PSP identification | STR 11 | O, mandatory only for defunding with different PSPs | CreditorAgent |
| Amount | NUM 18 | M | Amount |
| Unstructured remittance | STR 140 | O | UnstructuredRemittanceInformation |
| Transaction Identification ("End to End identification entered by the end-user") | STR 35 | O | EndToEndId |

Footnote (p.97): "transaction type" is called **"payment type" in Annex D2**. A mapping is needed, but the
coding is the same.

Balance check rule 5 (p.57): during manual funding, if "other incoming digital transactions are still being
processed … the manual funding process must be discontinued".

Downstream (all Spec #5): Funding/Defunding online settlement request creation, validation and processing
towards DESP (7.4); post-settlement (7.5); CBMA funds blocking, release, debit and credit (7.2); D€ account
debit and credit (7.3).

### 1.6 Automatic funding/defunding and waterfall settings (Liquidity settings service, 6.8, pp.63-75)

"An individual user who has successfully opened a digital euro payment account must have the ability to
configure automated funding and defunding operations." "Settings are managed at the level of the digital euro
end user."

- **Liquidity settings request validation** (6.8.1.1, pp.63-66), event "Liquidity settings request". Rules:
  - M: User ID or DEAN.
  - M: CREATE / UPDATE / DELETE. CREATE only if none exists; UPDATE/DELETE only if one exists.
  - Threshold funding: "Only Funding threshold amount is required". Defunding likewise.
  - Scheduled funding: if any of frequency, start date or amount is given, all three are required, and the
    "automated funding threshold must not be populated". The start date must be today or later. Same rules for
    defunding.

  Payload (all O except Type of request, M): Waterfall Indicator; Reverse waterfall indicator; Scheduled
  automated funding start date (`DateFrom`) / frequency (ISO Frequency7Code) / amount; Automated funding
  threshold (`Threshold`, "minimum balance level … that triggers an automated funding"); the same four for
  defunding (defunding threshold = "maximum balance level").

  Note: the incoming table does **not** contain User ID or DEAN, although rule 2 requires it.
- **Liquidity settings storage** (6.8.1.2, pp.66-68): store the parameters plus an amendment date. The stored
  list **says "Waterfall indicator (0 = activated / 1 = not activated)"**. This **contradicts** [DATA] p.65
  ("0 - Waterfall is not set / 1 - Waterfall is set"). The list also omits the scheduled defunding amount and
  the defunding threshold.
- **Liquidity settings removal** (6.8.1.3, pp.68-69): at offboarding.
- **Liquidity settings look-up** (6.8.1.4, pp.70-73), event "Liquidity settings look-up". It is called from the
  app or internally. The request has indicator flags for which settings to return (waterfall, reverse
  waterfall, scheduled funding, scheduled defunding, the thresholds, **Holdings limit indicator**). The
  response returns the settings plus **Holdings limit** ("Maximum amount of digital euro that can be held by
  an individual user", NUM 18). If no setting exists, the function assumes "not selected" and still
  succeeds.
- **Waterfall/Reverse Waterfall option check** (6.8.1.5, pp.73-75). Internal. If the PSP is the payer PSP
  and a funding amount is present but reverse waterfall is "NO", it rejects. If the PSP is the payee PSP and a
  defunding amount is present but waterfall is "NO", it rejects. Incoming: DEAN (M, `AccountIdentification`),
  Defunding amount (O), Funding amount (O).
- Definitions (p.73): "Waterfall for defunding in case of excessive funds, or Reverse Waterfall for funding in
  case of insufficient funds".

### 1.7 Balance enquiry (Fig.22 p.32, 6.4 pp.56-61)

App steps: "App Opening", "Select Online Balance Option", "Authentication", "Display Balance".

- **Digital euro payment account balance look-up** (6.4.1.2), event "digital euro payment account
  balance". Request:
  - DEAN, M.
  - Balance type `AVLB`, M (`BalanceType`).
  - Upcoming balance indicator, O.
- Response: balance type, indicator, balance date, **Available balance**, **Upcoming balance** (only if the
  indicator is 1), and **Holding limits**.
  - Upcoming balance = "Available balance – reserved funds – upcoming standing orders – upcoming recurring
    payments" (O for the PSP).
  - If only the available balance can be retrieved, the result is still "successful" with a dedicated reason
    code "to inform the user that only the available balance is provided" (rule 8).
- **Digital euro payment account Balance check** (6.4.1.1, internal): real-time check, minimum balance,
  "Balance availability check" (not reserved, concurrent transactions considered), holding-limit check.
  Insufficient funds or an exceeded holding limit means reject. Input: DEAN and Transaction amount.

### 1.8 P2P payments (Fig.11-14 pp.21-24, §8.1 pp.102-109)

App steps: DEAN (Fig.11): "App Opening", "DEAN Entry", "Amount Entry", "Authentication". Alias, payer side
(Fig.12): "App Opening", "Amount Entry", "Authentication", "Alias Entry". Alias, payee-initiated (Fig.13):
"App Opening", "Payment Details Entry" on the payee side, "Authentication" on the payer side.

PSP-side functions in each P2P figure, on both payer and payee PSP:
- Waterfall/Reverse Waterfall option check, balance look-up
- Funding/Defunding Settlement Service and post settlement
- Amount Assessment Service ("Pre-settlement payment / Post-settlement payment, Funding-defunding amount
  assessment")
- Fraud Risk Service ("Local Fraud & Risk Management", "Fraud & Risk Score Dispatch (DESP)")
- "Device Based Remote Authentication"
- Payment Processing (instruction creation or validation, settlement processing)
- CBMA status and balance check; CBMA funds blocking, release, debit and credit
- D€ account debit and credit, D€ account status check
- Payer side only: "PSP ID Look Up Dispatch" plus "DEAN Validity Check" for DEAN payments, or "Alias Look-Up
  Dispatch" for alias payments
- Notification Management

- **Individual user payment instruction initiation validation** (payer side, 8.1.1.6, pp.103-106), event
  "Individual user payment initiation".
  - Always required: Message Identifier, Event Identifier, Message date time, Transaction initiation Method,
    Transaction type, Transaction Amount, Transaction Currency, Transaction date, Merchant Category Code.
  - Transaction type must be **`PP01`**. MCC must be **`4829`** for P2P.
  - Optional user input: unstructured remittance, transaction identification.
  - QR code, pay-by-link or "NFC P2P" → Payee DEAN required.
  - Alias → payee alias type and value. If the alias is already resolved, also Payee DEAN and Payee PSP ID.
  - On success: generate a UETR (UUID v4 format) and store the transaction.
- **Payload** (one structure "for all the payment methods"):

  | Field | Type | Pres. | Standardised name |
  |---|---|---|---|
  | Transaction initiation method: "QR code / Pay-by-link / Alias / DEAN / NFC P2P", "Code set to be clarified" | STR 4 | M | PaymentMethod |
  | Transaction type (PP01, PB01, BP01, FU01, DF01) | STR 4 | M | TransactionType |
  | Transaction Amount | NUM 18 | M | Amount |
  | Transaction Currency (ISO 4217) | SSET 3 | M | Currency |
  | Transaction Date | Datetime UTC 24 | M | CreationDateTime |
  | Payee Name | STR 70 | O | Name |
  | Payee DEAN | STR 18 | O | |
  | Payee PSP ID | STR 11 | O | CreditorAgent |
  | Payee alias value | STR 2048 | O | ProxyAccount |
  | Payee alias Type | SSET 4 | O | ProxyAccountType |
  | Merchant Category Code (ISO 18245) | NSET 4 | M | MerchantCategoryCode |
  | Unstructured remittance | STR 140 | O | UnstructuredRemittanceInformation |
  | Transaction Identification | STR 35 | O | EndToEndId |

- **Individual user payment request initiation validation** (payee-initiated, 8.1.1.7, pp.106-109), event
  "Individual user payment request". It mirrors the instruction with Payer Name / Payer DEAN / Payer PSP ID
  (`DebtorAgent`) / Payer alias value and type.
- Common functions listed in 8.1 (Spec #5): DEAN validity check; Alias validity check; **"Alias look-up
  dispatch"**, which requests resolution from DESP "to retrieve payer's or payee's details (DEAN and PSP
  Identifier)"; **"PSP ID look-up dispatch"**, which requests from DESP the PSP identifier for a DEAN "for
  routing purpose"; **"Tokenisation request"** (QR or pay-by-link, "requests a token to DESP"); "Pay-by-link
  creation".

### 1.9 QR code and NFC

- **P2P QR** (Fig.14 p.24, image only). The payee app generates and displays the QR, and the payer scans it.
  PSP functions shown include a Tokenization Service "QR Code (De)tokenization Dispatch" on both sides
  towards the DESP "Tokenization Service". The QR data structure is n.s. here. [DATA] p.26 lists generic QR
  attributes for e-commerce (QR Code type static/dynamic, format, version, encoding, "QR code data structure
  (e.g., TLV, JSON)", refresh interval, security features).
- **Pay-by-link P2P**: "Placeholder for a future version of the document" (p.24).
- **NFC at POS** (Fig.15 p.25). App steps: "App Opening For NFC", "Display Digital Euro Card & Metadata",
  "Offline Authentication CDCVM", "Online Authentication CDCVM", "Wait for User To Tap Phone On POS",
  "Notification". Distributing PSP: "Mobile NFC Token Transaction service", with "NFC Cryptogram Check" and
  "NFC Token Mapping Look-Up", then "NFC CPACE Payment Request Validation". Acquiring PSP: "NFC CPACE Payment
  Request Creation". The HCE SDK sits in the app.
- **NFC enrolment / lifecycle** (6.10, pp.81-95).
  - Pre-requisite: the PSP has integrated the **ECB SDK (HCE SDK)** in the app and the **HCE SDK backend** in
    its back end. The reference is a placeholder (p.82).
  - Enrolment management (rules p.84):
    - check the account status;
    - optional internal fraud check;
    - retrieve the DEAN last 4 digits and its own PSP ID;
    - define Key Counter Limits;
    - call the HCE SDK backend's "NFC enrollment preparation API" (defined in the placeholder ECB
      guidelines) → receive a **Reference** (UUID 36) and return it to the app.
  - Key replenishment reference values (p.85):

    | Parameter | Min | Max |
    |---|---|---|
    | Max Sessions | 8 | 12 |
    | Trigger Replenishment Limit | 5 | 8 |
    | Force Replenishment Limit | 2 | 4 |

    These are "based on key usage counters, not on fixed time durations".
  - At the force limit while offline, the app "must integrate the notification mechanism provided by the HCE
    SDK" and prompt the user to reconnect.
  - Enrolment confirmation: the HCE SDK backend notifies the PSP with the "NFC token generated by the SEPI
    TSP". The PSP then performs **NFC token mapping registration**, linking the token to DEAN + PSP App ID.
  - Termination can be initiated by the app or by the PSP. The token mapping is then deregistered.
  - The Fig.3 app steps include "OS Redirection to allow the customer selecting the NFC digital Euro Wallet by
    Default" and "OS Redirection to allow the customer activating the NFC Feature".
  - Interface list from the image on p.83: Online authentication request/response; NFC enrolment Request;
    NFC enrolment preparation request with credential data; … confirmation with ref number; NFC enrolment
    ref number; NFC enrolment request with ref number; EMV CPACE Perso script; … execution; …
    confirmation; Token activation confirmation; NFC service enrolment confirmation. DESP SEPI side:
    "Tokenization Service (Token generation)", "Data prep service (EMV CPACE perso Script generation)".
- **NFC payment** (8.5, pp.129-131): the PSP sends an "NFC cryptogram verification request to the DESP-SEPI"
  ([Refer to D2 Annex]), then maps the token to DEAN + PSP App ID. E2E reference: "TM-1.6 Online contactless
  SoftPOS payment with mobile device or wearable - same PSP".

### 1.10 Transaction history (Fig.23 p.33, 8.4 pp.125-128)

App steps: "App Opening", "Select Transaction History Option", "Enter Criteria", "Authentication", "Display
History".

- Request, event "Transaction history request": Transaction type (PP01/PB01/BP01/FU01/DF01, M), Transaction
  Start Date / End Date (O), Transaction Identification / EndToEndId (O). "The format and consistency checks
  performed by the Mobile App are not duplicated in the service."
- Look-up rules: the date-range logic is inclusive. With no dates, all transactions are returned, and "The
  PSP has the ability to determine how much history is included". If nothing matches, a reason code is
  returned.
- Response, per transaction:
  - Transaction type "Purchase / Refund / Reservation / Account-to-account" ("List to be confirmed and code
    set to be clarified"; note the inconsistency with PP01 etc. in the request)
  - Amount, Currency, Date
  - "Payee Name / Merchant Name" (O)
  - **Digital euro account number of the payee (M)**
  - EndToEndId (O)
- [RB] p.94 fn 40: "Transaction history will only be available for online digital euro payments."

### 1.11 Notifications (6.9 pp.75-81, plus the Spec #5 Notification service)

- **Notification settings request validation** (6.9.1.1). The event string is given as "Liquidity settings
  request" (copy-paste error in the source, p.77). Rules: User ID or DEAN; CREATE/UPDATE/DELETE logic as for
  liquidity settings.
- Payload:
  - Type of request (M).
  - **Communication channel type**: SSET 4 M `CommunicationMethodCode`, `EMAL` / `ONLI` (in-app) / `MBNO` /
    `MULT`.
  - **Communication channel value**: STR 140 M.
  - Optional BOOL event flags: D€ account credit event, D€ account debit event, Waterfall transaction event,
    Reverse waterfall transaction event, Automated funding transaction event, Automated defunding
    transaction event, Threshold based transaction event.
- Storage: False = opt-out, True = opt-in, plus an amendment date. Removal happens at offboarding.
- The "User's notification" common service (p.39) informs the user "confirming (or not) the proper execution
  of the transaction".
- [DATA] adds, for business users only (AM-1.2): aggregated notifications indicator and frequency, and
  per-event aggregation (pp.52, 56, 61, 65). Notification settings entity (p.16): type, channel type and
  details, trigger, content customisation, delivery and retry policy, priority and queuing, expiration.

### 1.12 Blocking / unblocking (6.5 p.61)

Listed functions: "Digital euro payment account (un)blocking request validation" ("sent by the end-user's
device"), "Digital euro payment account blocking", "Digital euro payment account unblocking" (Spec #5). **No
message here.** [DATA] p.64 Type of request includes `UNBL` (Unblocking account request) and `BLCK` (Blocking
account request). Account status code set: `ACTV`, `BLCK`, `CLSD`, `SSPD` ("Code set to be confirmed",
[DATA] p.56). Fig.2 app step: "Digital Euro Account Management".

### 1.13 User lifecycle / amendments (Fig.2 p.12, 6.2.1.5 p.50)

App steps: "App Opening", "Authentication", "Alias Management", "CBMA Link Management", "Liquidity Settings",
"Notification Settings", "Digital Euro Account Management". Amendment: "The user data that can be modified is
the same as those currently editable. The already existing functions are reused without any modification."

### 1.14 Offboarding (Fig.8 p.18, 6.2.1.6-6.2.1.7 pp.50-54)

App steps: "App Opening", "Authentication", "Offboarding Request", "Enter CBMA".

- **Offboarding request validation**, event "Individual user offboarding". Payload: DEAN (STR 18, O) and/or
  Identifier of the digital euro user (STR TBD, O). Rule 2 requires one of the two.
- **Rule 4 (M)**: reject if there are open pre-disputes or disputes, or "pre-reservations still pending".
  Otherwise update the user status "to reflect the ongoing offboarding".
- Fig.8 PSP steps: Balance Holding Limit Check / D€ Account Balance Look-Up; NFC Token Termination; Liquidity
  Settings Removal; Notification Settings Removal; "Defunding online settlement request/processing" (D€
  Account Debit → CBMA Status check → CBMA Credit); Digital Euro Account Blocking Request; **"DEAN
  Deregistration& PSP Mapping Removal"**; User Deregistration; "Digital Euro User Deactivation"; CBMA Look-up;
  Linked CBMA Settings Removal; Notification Management.
- **Digital euro individual user deregistration** (6.2.1.7, pp.52-54). Activated by the DESP's
  confirmation, Annex D2 **`"PUT/ deans – Response"`**. Steps: check and remove the CBMA link; remove the
  liquidity and notification settings; "request the digital euro user deactivation" (Spec #5). On success:
  status **"CLOSED"** and the closing date is set.

### 1.15 Switching

Not specified in [PSP] beyond the existence check: "the user must be requested to perfom an account
switching" (p.55). [RB] p.94: switching UI is in Spec #3 5.2.2.2. [RB] (p.99) DESP AM "Switching" keeps "the
same Digital Euro Account Number". [DATA] recurring-payment and standing-order entities carry a "parameters
transfer indicator" for account switching (pp.14-15).

### 1.16 Standing orders (Fig.16-21 pp.26-31, 8.3 pp.111-124)

- Set-up request (event "Standing order set-up request"):
  - M: amount, frequency (ISO Frequency7Code), start date (`DateFrom`), and either payee alias (type and
    value) or payee DEAN.
  - O: end date, unstructured remittance.
  - An alias triggers an alias look-up. A DEAN triggers a DEAN validity check, then a PSP ID look-up.
- Overview, update (amount, payee DEAN or alias, frequency), termination (end-date M), upcoming payments
  (returns the next amount, date and payee name).
- Periodic transaction: the payer PSP does the alias resolution (if an alias was used), requests the
  central fraud score, runs the local fraud check, checks the balance (reverse waterfall), sends the payment
  to DESP, then receives the status and notifies. The payee PSP validates the DESP request, checks for
  waterfall, responds and notifies.

### 1.17 Recurring payments (8.2 pp.109-111)

Only "User and authorisation details storage" is specified. The incoming message is "Placeholder for Annex D2
reference".

---

## 2. PSP ↔ DESP messages referenced in these documents

**[PSP] and [DATA] do not define PSP↔DESP message schemas.** They only reference them:

| Context | What [PSP] says | Where specified |
|---|---|---|
| Existence check, other PSP | "check if the user is already registered in DESP" | Annex D2: `"GET/ users/{userID} – Request" \| "GET/ users/{userID} – Response"` (p.55) |
| Alias registration for a DEAN (create/update/delete) | "must submit a registration request to the DESP" | Annex D2: `"GET/ users /{userID} – Request" \| "GET/ users /{userID}– Response"` (p.45, quoted as written) |
| DEAN registration | "The PSP requests a DEAN to DESP and stores it." | Spec #5 Common services (pp.35, 61). Back-end in Annex D2 (inference) |
| DEAN deregistration + PSP mapping removal | "requests to DESP the deregistration of the … DEAN and the removal of its mapping to the PSP" | Spec #5 (p.35). Confirmation = Annex D2 `"PUT/ deans – Response"` (p.53) |
| Digital euro user deactivation | "request the digital euro user deactivation" | "Specifications#5 – Digital euro user deactivation" (p.53) |
| Alias look-up dispatch | resolution to DESP → DEAN + PSP Identifier | Spec #5. DESP "Alias Lookup Service" |
| PSP ID look-up dispatch | PSP ID for a DEAN "for routing purpose" | Spec #5 |
| Tokenisation request | QR / pay-by-link token from DESP | Spec #5. DESP "Tokenization Service" / SEPI |
| Fraud and risk score dispatch | "requests a risk score to DESP" | Spec #5 |
| Funding/Defunding online settlement request + processing | "sends a funding online request to DESP" | Spec #5 |
| Payment settlement processing / payment request validation | send to DESP / receive from DESP | Spec #5 6.2 |
| NFC cryptogram check | "verification request to the DESP-SEPI" | "D2 Annex" (p.130) |
| NFC token | "NFC token generated by the SEPI TSP", relayed via the HCE SDK backend | ECB HCE SDK guidelines (placeholder) |

**Onboarding sequence**, reconstructed from Fig.1 + §6.2/6.3 + [RB] AM-011 (order partly inference, since
Fig.1 is "not a sequence diagram"):

1. App → PSP: authenticate (SCA, PSP-specific).
2. App → PSP: "Digital euro user registration" (`CashAccountType=DEUR`) → registration request validation.
3. PSP internal: existence check, same PSP (status ≠ Closed).
4. PSP → DESP: `GET /users/{userID}` (registered elsewhere? → switching).
5. PSP internal: create the user envelope (user ID, technical proof, entry ID; status PENDING; type INDI;
   link to PSP App ID).
6. PSP → DESP: DEAN registration; the user is registered in the DESP "including the mapping to itself as the
   corresponding PSP and including a potential alias" ([RB] AM-011-005).
7. Optional: alias (validation → ownership proof → DESP registration), CBMA link, liquidity settings,
   notification settings.
8. PSP → App: DEAN + technical proof ([RB] AM-011-006), then a notification.

**Where onboarding/access-management messages are specified:**
- App-side UI: **Annex D1 Spec #3** §4.2.1 (PSP app) and §5.2.1.1 (online banking) ([RB] pp.93-94).
- PSP functions: [PSP] §6 (this document).
- Common functions (DEAN registration, deregistration, user deactivation, linked account): **Annex D1 Spec
  #5**.
- PSP↔DESP API: **Annex D2 Back-end implementation specifications**. [RB] §4.4.3 (p.99) lists the DESP
  "Access management service (AM)" functions: "User registration and management", "DEAN creation and
  management", "Alias registration and management", "Switching". Also "Alias Lookup Service (AL)".
- Of the attached D2 files (#6 Data exchange, #7 Settlement, #8 Data dictionary), **none is the
  access-management back-end spec**. D2 #6 only has related reports and queries (repository data query by
  user ID or hashed technical proof; account data query; changes of "DEAN (added/deactivated/deleted)",
  "proxy alias", "user data (user ID, hashed technical proof)") ([D2-6] pp.5-6). The `/users` and `/deans`
  endpoints must be in a D2 document that was not provided.

---

## 3. Data management (who stores and sees what)

### 3.1 What [DATA] actually says (and does not say)

- It is **an illustrative front-end data model**: "corresponds only to the front-end view. However, some
  entities belonging to DESP domain are reflected" (p.8). "Entities managed by DESP are not described in this
  document" (pp.16, 28, 37, 41). "It is not intended to represent the entirety of an information system"
  (p.7).
- **No retention periods** are defined anywhere in [DATA] or [PSP]. **No general pseudonymisation scheme
  and no party-by-party visibility matrix** are defined either. Only scattered statements exist, listed in
  3.3.
- The data dictionary (§5, pp.42-65) has the columns "New for digital euro", "Used by internal process
  only" and **"Visible to the end-user"** (definition p.42: "Data entered by the end-user or displayed to the
  end-user"). All attribute IDs are "AT#" (not yet numbered).
- Process IDs used in the dictionary (useful to cross-reference the Annex B2 E2E flows):
  - Access management: "AM-1.1 & sAM-26 Onboarding of individual user", "AM-1.2 Onboarding of business
    user", "AM-4.1.x End-user (individual) amendments", "AM-4.1.9 … alias registration".
  - Liquidity management: "LM-1.1 Online manual funding", "LM-2.1 Online manual defunding".
  - Transaction management: "TM-1.6 Online contactless SoftPOS payment with mobile", "TM-2.1/2.2/2.3"
    e-commerce (QR / alias or DEAN / pay-by-link), "TM3 – P2P payments", "TM-3.1 P2P payment with QR code
    in-app", "TM-3.7 P2P payment with payment request by link", "TM-3.9 Transactions history", "TM-3.10 &
    TM-3.11 P2P payments with DEAN", "TM-4.x" recurring/standing order, "TM-5.x" pre-authorisation, "TM-7.2
    Refund (e-commerce)", "TM-9.1 Balance enquiry mobile app – Online balance".

### 3.2 Identifiers: user identifier, technical proof, end-user entry, DEAN, alias

| Item | Definition (exact) | Notes |
|---|---|---|
| **Digital euro user identifier** | "Unique identifier of an digital euro user" ([DATA] p.11). Dictionary: STR, length **TBD**, new / internal / visible (p.57) | Generated by the distributing PSP at registration. Rules are a "(placeholder)" ([PSP] p.49). Linked to the PSP App ID. |
| **Technical proof** | "Used to derive settlement ledger identifier(s) for the user's digital euro holdings. **A hashed version is stored by the DESP** to enable validation of emergency portability request" ([DATA] p.11). "generated at end-user onboarding to prove the ownership of the user's digital euro holdings" (p.13). Dictionary: "Cryptographic root key used to prove the ownership of holdings", STR **TBD**, new / internal / **visible to end-user** (p.63) | Entity fields: identifier, technical proof, opening / provision / closing dates (pp.13-14). Individual: 1 proof → 1 entry. Business: 1 proof → several entries (p.19). [RB] AM-011-006: shared with the user. [D2-6]: "Hashed technical proof … STR 32". |
| **End-user entry** | "used to identify the user's digital euro holding within the settlement ledger" ([DATA] p.14) | Generated by the technical proof. 1 entry ↔ 1 D€ account (p.10). The entry identifier rules are a "(placeholder)" ([PSP] p.49). |
| **DEAN** | "Unambiguous identification of the digital euro payment account of the end-user (payer or payee)" ([DATA] p.13). STR 18 (p.56) | Managed by exactly one distributing PSP (p.10). Last 4 digits are printed on the receipt. |
| **Alias** | "unique pseudonymous identifier used to protect user's identity … that can only be attributable to an identifiable natural or legal person by the payment service provider distributing the digital euro or by the digital euro user. An alias is expected to be the primary identifier shared in transactions with alias" ([DATA] p.12) | Types EMAL / MBNO. Value STR 2048. The DESP holds the alias↔DEAN link ([PSP] p.45). |
| PSP App ID | n.s. as a data element. Used in "link the Digital Euro User Identifier with the PSP App ID" and in the NFC token ↔ DEAN ↔ PSP App ID mapping ([PSP] pp.49, 87) | |
| UETR / End-to-End id | UETR = UUID v4, generated by the initiating PSP ([PSP] pp.97, 104). "Transaction identifier … assigned by the PSP initiating the transaction for its own need" vs "End-to-End transaction identifier … known by both PSP" ([DATA] pp.31-32) | |

Status code sets:
- User status `PEND` / `ACTV` / `CLSD` ("Code set to be defined", [DATA] p.57). [PSP] uses PENDING and
  CLOSED. [DATA] p.12 also mentions prospect / active / inactive / suspended / closed.
- Account status `ACTV` / `BLCK` / `CLSD` / `SSPD`.
- User type `INDI` / `BUSI`.

### 3.3 Visibility matrix (only what the documents state; the rest is "n.s.")

Columns: **App** = the user's device / PSP app; **D-PSP** = the user's own distributing PSP; **Cpty PSP** =
the counterparty's PSP in a payment; **Acq/Merchant** = acquiring PSP / merchant; **DESP** = Eurosystem
platform.

| Data | App / user | D-PSP (own) | Cpty PSP | Acq / Merchant | DESP | Source |
|---|---|---|---|---|---|---|
| KYC identity data | provides | yes, existing KYC process "not modified" | n.s. | n.s. | n.s. | [PSP] p.46 |
| Digital euro user identifier | visible | creates, stores, links to PSP App ID | n.s. | n.s. | queried by `GET /users/{userID}`. [D2-6]: user ID in DESP repository | [PSP] pp.49, 55. [DATA] p.57 |
| Technical proof | visible (must be shared, [RB]) | generates (rules placeholder) | n.s. | n.s. | **hashed version only** | [DATA] pp.11, 63 |
| End-user entry id | n.s. | in user envelope | n.s. | n.s. | used in settlement ledger | [PSP] p.49. [DATA] p.14 |
| DEAN | visible | stores and manages | payer/payee DEAN in P2P messages. Payee DEAN shown in payer's history | Merchant DEAN. **DEAN last 4 digits on receipt** | DEAN registered at DESP. PSP ID look-up by DEAN | [PSP] pp.35, 40, 85, 128. [DATA] pp.55-58 |
| Alias | visible | registers. **Only D-PSP or user can link alias → person** | payer/payee alias in P2P messages | n.s. | holds alias↔DEAN link. Look-up returns DEAN + PSP ID | [DATA] p.12. [PSP] pp.45, 102 |
| Payer / payee name | visible | P2P message fields (O) | P2P message fields (O) | Payee trade name / location for e-commerce | n.s. | [PSP] pp.105, 108. [DATA] p.58 |
| Linked CBMA (IBAN) | visible | stores link. CBMA services | n.s. | n.s. | n.s. for individuals. For business users: IBAN "used for external processing with DESP" | [PSP] p.62. [DATA] p.23 |
| Balance, holding limit | visible | retrieves and checks | n.s. | n.s. | holdings in settlement ledger (location of balance n.s. here) | [PSP] pp.56-61 |
| Liquidity settings | visible | stores ("at the level of the digital euro end user") | – | – | no DESP message defined | [PSP] p.63 |
| Notification settings | visible | stores | – | – | no DESP message defined | [PSP] p.76 |
| Device id / type / IP | n.s. | in model (illustrative) | n.s. | acceptance device data internal to acquirer | n.s. | [DATA] pp.12, 24 |
| Merchant Category Code | – | receives it **encrypted** | – | manages | receives it **encrypted** | [DATA] p.23 ("Only the merchant category code is transmitted in the payment request to the DESP and distributing PSP, and it is encrypted.") |
| POI, location, activity type, acceptance device, keyboard, authentication traceability | – | – | – | **"managed internally by the acquiring PSP solely for purposes of traceability, audit …"** | – | [DATA] pp.22-28 |
| Fraud & risk score | – | combines central + local score | n.s. | n.s. | provides central score | [PSP] p.36 |
| NFC token ↔ DEAN ↔ PSP App ID | – | stores mapping | – | token via POS | token generated by SEPI TSP. Cryptogram check | [PSP] pp.38, 86-87, 130 |
| Transaction (amount, date, remittance, type) | visible | stores transaction + UETR | own side | own side | "DESP transaction" (contents n.s. here) | [PSP] p.104. [DATA] pp.31, 37 |
| Dispute data | initiates | forwards to payee | payee responds | – | n.s. here | [DATA] pp.38-41 |

**Pseudonymisation mechanisms mentioned:**
- Alias, a pseudonymous identifier.
- Hashed technical proof at the DESP.
- Encrypted MCC.
- NFC token, a surrogate value ([RB] p.100 "Contactless (NFC) surrogate value").
- QR / pay-by-link tokens issued by the DESP Tokenization Service.

**Retention: n.s.** Lifecycle dates (creation, amendment, closing; opening, provision, closing) are kept
"Needed for lifecycle traceability" ([DATA] pp.11-14). Storage rules say "Only new or updated information must
be stored" plus an amendment date ([PSP] pp.67, 79, 119). The PSP decides how much history to show ([PSP]
p.127).

### 3.4 Data dictionary "visible to the end-user" (useful for app screens)

Derived from the column flags on [DATA] pp.52-65:

- **Visible:**
  - Identity and account: Identifier of the digital euro user, Technical proof, DEAN, Digital Euro User
    Status, Holding limit, D€ balance, upcoming balance.
  - Liquidity and notifications: all liquidity and notification settings fields, Communication channel type
    and value.
  - Account fields: Non-digital euro payment account (IBAN) and balance, Credited/Debited Account
    Identification.
  - Payment fields: Payee/Payer DEAN, alias type and value, name, PSP ID, PSP identification, Payee location
    and trade name, Merchant DEAN, Transaction amount, currency, date, identification, initiation method,
    Unstructured remittance, Payment link.
  - Other: standing order and recurring fields, reservation fields, Refund Amount, Type of request, Language,
    Alias ownership indicator, **DEAN last four Digits** (new, visible, not internal).
- **Internal only (not visible):**
  - Account and user state: Digital euro payment account status, Digital Euro User Type, Indicator of already
    existing DEAN, Linked account indicator.
  - Message fields: message, event and incoming-message identifiers, Return code, Reason code, Urgency Level,
    Settlement confirmation status.
  - Payment internals: Merchant identification, PSP BICs of debited and credited accounts, Funding /
    Defunding / Incremental amounts, Funds release, QR code, Reference (NFC), Token, all EMV tags.
- **No flag at all:** Merchant Category Code.

---

## 4. UX and branding rules relevant for a simulated app

- **[PSP] and [DATA] contain no branding, logo, naming or mandatory-wording rules.** [RB] (pp.92-94) says
  these are in **Annex D1 Spec #3**. PSP app §4.1.1 "Functional requirements" includes "user experience,
  accessibility, personalised settings, QR code service, NFC communication, user authentication, user
  activation, user alerts, and visual consistency and branding". Online banking §5.1.1 covers "seamless
  navigation, responsive design, visual consistency and branding …". **Spec #3 is needed for this point.**
- Terminology to use verbatim:
  - "digital euro payment account"
  - "digital euro payment account number (DEAN)"
  - "non-digital euro payment account" (CBMA)
  - "PSP App" (bank app) vs "D€ App" (separate ECB app, in the intro diagram p.9; future rulebook)
  - "funding" / "defunding"
  - "waterfall" / "reverse waterfall"
  - "holding limit(s)"
  - "available balance" / "upcoming balance"
  - "alias"
  - "standing order"
- Screens and steps named in the figures: see the per-journey "App steps" lists in §1. They are a good
  skeleton for the simulated app's navigation.
- Fields to display:
  - Balance screen: available balance, upcoming balance, holding limit, plus the partial-result reason-code
    message (p.59).
  - Onboarding result: DEAN and technical proof.
  - History: type, amount, currency, date, payee or merchant name, payee DEAN, EndToEndId.
  - NFC card view: "Display Digital Euro Card & Metadata", DEAN last 4 digits.
- MBNO alias input must be strict E.164 (`+` and digits only) (p.43).
- POS rejection messages (codes 001-022, e.g. "009 Not enough balance in the account → Insufficient funds")
  are POS display texts, "to be translated into the language of the acceptance device" ([DATA] pp.25-26). They
  are useful for the merchant gateway simulation.
- NFC AID `A0000009580110`, AID label "Digital euro payment account online AID (to be confirmed)". Amount range
  in cents: 00000001-99999999 ([DATA] p.25).

---

## 5. Placeholders, TBDs and inconsistencies

**Placeholders and TBDs**
- Generation rules for the user identifier, technical proof and entry identifier: "(placeholder)" ([PSP]
  p.49). Length TBD for the user identifier and technical proof ([PSP] pp.50, 51, 69, 80. [DATA] pp.57, 63).
- `CashAccountType` "DEUR" "(to be confirmed)" ([PSP] p.47. [DATA] p.64).
- Pay-by-link P2P: "Placeholder for a future version of the document" ([PSP] p.24).
- HCE SDK / HCE SDK backend: "[Placeholder for … ECB implementation guidelines]". NFC E2E flows are
  placeholders ([PSP] pp.82-95). The NFC sequence diagrams "are temporary" ([PSP] p.129).
- Recurring payment incoming message: "Placeholder for Annex D2 reference" ([PSP] p.110).
- Transaction initiation method: "Code set to be clarified" ([PSP] pp.105, 108). [DATA] p.64 also has "Code
  set to be defined".
- History transaction type list "to be confirmed and code set to be clarified" ([PSP] p.128).
- Code sets "to be confirmed" or "to be defined":
  - Communication channel type ([DATA] p.54)
  - Account status (p.56)
  - User status (p.57)
  - Recurring update reason code (p.60)
  - Type of request (p.65)
- Digital euro contract identifier length TBD ([DATA] p.56). Issuer Application Data "Other data to be
  defined" (p.58). Token "To be decided for Digital Euro but should be 16 digits" (p.63). AID label "(to be
  confirmed)" (p.25).
- Variable-amount recurring payments "will not be offered at digital euro launch" ([DATA] pp.14, 60).
- Aliases "at launch may be limited to one" ([DATA] p.9).
- Yellow-highlighted placeholders exist throughout, but the highlighting is not visible in the extracted text
  (Preamble).
- Authentication services, Spec #6 technical standard, and dispute specs: future versions ([RB] pp.94, 97).

**Inconsistencies to be aware of (copy faithfully or decide explicitly)**
- Waterfall indicator: "0 = activated / 1 = not activated" ([PSP] p.67) vs "0 - Waterfall is not set / 1 -
  Waterfall is set" ([DATA] p.65) vs "set to 'NO'" ([PSP] p.74).
- The alias registration for DEAN references `GET/ users /{userID}` (p.45), which is the same reference as
  the existence check.
- The notification settings event id reads "Liquidity settings request" (p.77).
- The liquidity settings request requires User ID or DEAN, but the table has no such field (pp.64-66).
- The liquidity storage list omits the scheduled defunding amount and the defunding threshold (p.67).
- History request types (PP01…) vs response types (Purchase / Refund / Reservation / Account-to-account)
  ([PSP] pp.126, 128). [DATA] p.32 has Type = Purchase / Refund / Reservation / Account-to-account.
- "Transaction type" (D1) = "payment type" (D2) (footnotes pp.97, 105, 108, 126).
- [DATA] p.24 calls the DEAN "non-digital euro payment account number (DEAN)" (typo).
- Fig.8 shows "Digital Euro Account Unblocking" during offboarding (probably meant blocking; inference).

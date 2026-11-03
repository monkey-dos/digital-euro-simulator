# Anna (PSP A) pays Ben (PSP B) 50 EUR

Payer-initiated payment between two banks (Annex D2-7 Fig. 7). DESP forwards the instruction to PSP B, which adds Ben's ledger entry, then settles and pushes the status to both banks. Ben's DEAN and both names travel encrypted for PSP B; in the payment messages DESP only sees bank codes, amount, payment type and entries.

| Step | From → to | What | File |
|---|---|---|---|
| 0 | Banking App A → PSP A | Anna asks her bank to pay Ben 50.00 EUR | [00-app-payment-initiation.json](00-app-payment-initiation.json) |
| 1 | PSP A → DESP | Which bank serves +4915100000003? *(placeholder)* | [01-alias-lookup-request.json](01-alias-lookup-request.json) |
| 2 | DESP → PSP A | Ben's DEAN, served by PSP B *(placeholder)* | [02-alias-lookup-response-200.json](02-alias-lookup-response-200.json) |
| 3 | PSP A → DESP | Payment instruction to the central platform | [03-desp-post-payment-instructions.json](03-desp-post-payment-instructions.json) |
| 4 | DESP → PSP A | Received and technically valid | [04-desp-response-201.json](04-desp-response-201.json) |
| 5 | DESP → PSP B | Forwarded to Ben's bank | [05-psp-api-forward-to-payee-bank.json](05-psp-api-forward-to-payee-bank.json) |
| 6 | PSP B → DESP | PSP B accepts and adds Ben's ledger entry | [06-psp-api-response-201.json](06-psp-api-response-201.json) |
| 7 | DESP → DESP ledger | Settle: Anna −50, Ben +50 | [07-ledger-settlement.json](07-ledger-settlement.json) |
| 8 | DESP → PSP A | Final status to PSP A: settled | [08-psp-api-status-push-payer-bank.json](08-psp-api-status-push-payer-bank.json) |
| 9 | PSP A → DESP | Status received | [09-psp-api-204-psp-a.json](09-psp-api-204-psp-a.json) |
| 10 | DESP → PSP B | Final status to PSP B: settled | [10-psp-api-status-push-payee-bank.json](10-psp-api-status-push-payee-bank.json) |
| 11 | PSP B → DESP | Status received | [11-psp-api-204-psp-b.json](11-psp-api-204-psp-b.json) |
| 12 | PSP A → Banking App A | Anna's app shows: paid | [12-app-response.json](12-app-response.json) |

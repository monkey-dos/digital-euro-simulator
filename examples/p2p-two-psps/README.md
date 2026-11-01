# Anna (PSP A) pays Ben (PSP B) 50 EUR

Payer-initiated payment between two banks (Annex D2-7 Fig. 7). DESP forwards the instruction to PSP B, which adds Ben's ledger entry, then settles and pushes the status to both banks. Ben's DEAN and both names travel encrypted for PSP B; in the payment messages DESP only sees bank codes, amount, payment type and entries.

| Step | From → to | What | File |
|---|---|---|---|
| 0 | Banking App A → PSP A | Anna asks her bank to pay Ben 50.00 EUR | [00-app-payment-initiation.json](00-app-payment-initiation.json) |
| 1 | PSP A → DESP | Which bank serves +4915100000003? *(placeholder)* | [01-alias-lookup.json](01-alias-lookup.json) |
| 2 | PSP A → DESP | Payment instruction to the central platform | [02-desp-post-payment-instructions.json](02-desp-post-payment-instructions.json) |
| 3 | DESP → PSP A | Received and technically valid | [03-desp-response-201.json](03-desp-response-201.json) |
| 4 | DESP → PSP B | Forwarded to Ben's bank | [04-psp-api-forward-to-payee-bank.json](04-psp-api-forward-to-payee-bank.json) |
| 5 | PSP B → DESP | PSP B accepts and adds Ben's ledger entry | [05-psp-api-response-201.json](05-psp-api-response-201.json) |
| 6 | DESP → DESP ledger | Settle: Anna −50, Ben +50 | [06-ledger-settlement.json](06-ledger-settlement.json) |
| 7 | DESP → PSP A | Final status to PSP A: settled | [07-psp-api-status-push-payer-bank.json](07-psp-api-status-push-payer-bank.json) |
| 8 | PSP A → DESP | Status received | [08-psp-api-204-psp-a.json](08-psp-api-204-psp-a.json) |
| 9 | DESP → PSP B | Final status to PSP B: settled | [09-psp-api-status-push-payee-bank.json](09-psp-api-status-push-payee-bank.json) |
| 10 | PSP B → DESP | Status received | [10-psp-api-204-psp-b.json](10-psp-api-204-psp-b.json) |
| 11 | PSP A → Banking App A | Anna's app shows: paid | [11-app-response.json](11-app-response.json) |

# Anna pays Clara 25 EUR (same bank)

Both users bank with PSP A, so the central platform settles directly (Annex D2-7 Fig. 5). No encrypted part is sent: in the payment messages DESP receives no names and no DEANs, only ledger entries, bank codes and the amount. (The alias lookup in steps 1–2 is a separate service of the platform.)

| Step | From → to | What | File |
|---|---|---|---|
| 0 | Banking App A → PSP A | Anna asks her bank to pay Clara 25.00 EUR | [00-app-payment-initiation.json](00-app-payment-initiation.json) |
| 1 | PSP A → DESP | Which bank serves +4915100000002? *(placeholder)* | [01-alias-lookup-request.json](01-alias-lookup-request.json) |
| 2 | DESP → PSP A | Clara's DEAN, served by PSP A *(placeholder)* | [02-alias-lookup-response-200.json](02-alias-lookup-response-200.json) |
| 3 | PSP A → DESP | Payment instruction to the central platform | [03-desp-post-payment-instructions.json](03-desp-post-payment-instructions.json) |
| 4 | DESP → PSP A | Received and technically valid | [04-desp-response-201.json](04-desp-response-201.json) |
| 5 | DESP → DESP ledger | Settle: Anna −25, Clara +25 | [05-ledger-settlement.json](05-ledger-settlement.json) |
| 6 | DESP → PSP A | Final status: settled | [06-psp-api-status-push.json](06-psp-api-status-push.json) |
| 7 | PSP A → DESP | Status received | [07-psp-api-204.json](07-psp-api-204.json) |
| 8 | PSP A → Banking App A | Anna's app shows: paid | [08-app-response.json](08-app-response.json) |

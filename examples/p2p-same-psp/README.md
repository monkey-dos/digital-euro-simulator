# Anna pays Clara 25 EUR (same bank)

Both users bank with PSP A, so the central platform settles directly (Annex D2-7 Fig. 5). No encrypted part is sent: in the payment messages DESP receives no names and no DEANs, only ledger entries, bank codes and the amount. (The alias lookup in step 1 is a separate service of the platform.)

| Step | From → to | What | File |
|---|---|---|---|
| 0 | Banking App A → PSP A | Anna asks her bank to pay Clara 25.00 EUR | [00-app-payment-initiation.json](00-app-payment-initiation.json) |
| 1 | PSP A → DESP | Which bank serves +4915100000002? *(placeholder)* | [01-alias-lookup.json](01-alias-lookup.json) |
| 2 | PSP A → DESP | Payment instruction to the central platform | [02-desp-post-payment-instructions.json](02-desp-post-payment-instructions.json) |
| 3 | DESP → PSP A | Received and technically valid | [03-desp-response-201.json](03-desp-response-201.json) |
| 4 | DESP → DESP ledger | Settle: Anna −25, Clara +25 | [04-ledger-settlement.json](04-ledger-settlement.json) |
| 5 | DESP → PSP A | Final status: settled | [05-psp-api-status-push.json](05-psp-api-status-push.json) |
| 6 | PSP A → DESP | Status received | [06-psp-api-204.json](06-psp-api-204.json) |
| 7 | PSP A → Banking App A | Anna's app shows: paid | [07-app-response.json](07-app-response.json) |

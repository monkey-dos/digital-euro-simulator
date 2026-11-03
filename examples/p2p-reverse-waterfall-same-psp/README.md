# Anna pays Clara 150 EUR with only 120 EUR on her account

Reverse waterfall at the same bank (Annex D2-7 Fig. 11). The missing 30 EUR are taken from Anna's giro account and turned into digital euro in the same atomic step as the payment. The bank's central bank money account (DCA) pays for the new digital euro.

| Step | From → to | What | File |
|---|---|---|---|
| 0 | Banking App A → PSP A | Anna asks her bank to pay Clara 150.00 EUR | [00-app-payment-initiation.json](00-app-payment-initiation.json) |
| 1 | PSP A → DESP | Which bank serves +4915100000002? *(placeholder)* | [01-alias-lookup-request.json](01-alias-lookup-request.json) |
| 2 | DESP → PSP A | Clara's DEAN, served by PSP A *(placeholder)* | [02-alias-lookup-response-200.json](02-alias-lookup-response-200.json) |
| 3 | PSP A → PSP A core banking | Block 30.00 EUR on Anna's giro account | [03-giro-block.json](03-giro-block.json) |
| 4 | PSP A → DESP | Payment instruction with funding part | [04-desp-post-payment-instructions.json](04-desp-post-payment-instructions.json) |
| 5 | DESP → PSP A | Received: payment and funding technically valid | [05-desp-response-201.json](05-desp-response-201.json) |
| 6 | DESP → DESP ledger | Settle: DCA A −30, Anna +30 −150, Clara +150 | [06-ledger-settlement.json](06-ledger-settlement.json) |
| 7 | DESP → PSP A | Final status: payment and funding settled | [07-psp-api-status-push.json](07-psp-api-status-push.json) |
| 8 | PSP A → DESP | Status received | [08-psp-api-204.json](08-psp-api-204.json) |
| 9 | PSP A → PSP A core banking | Debit 30.00 EUR from Anna's giro account | [09-giro-debit.json](09-giro-debit.json) |
| 10 | PSP A → Banking App A | Anna's app shows: paid, 30 EUR topped up from giro | [10-app-response.json](10-app-response.json) |

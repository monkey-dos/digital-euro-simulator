# Anna pays Clara 150 EUR with only 120 EUR on her account

Reverse waterfall at the same bank (Annex D2-7 Fig. 11). The missing 30 EUR are taken from Anna's giro account and turned into digital euro in the same atomic step as the payment. The bank's central bank money account (DCA) pays for the new digital euro.

| Step | From → to | What | File |
|---|---|---|---|
| 0 | Banking App A → PSP A | Anna asks her bank to pay Clara 150.00 EUR | [00-app-payment-initiation.json](00-app-payment-initiation.json) |
| 1 | PSP A → DESP | Which bank serves +4915100000002? *(placeholder)* | [01-alias-lookup.json](01-alias-lookup.json) |
| 2 | PSP A → PSP A core banking | Block 30.00 EUR on Anna's giro account | [02-giro-block.json](02-giro-block.json) |
| 3 | PSP A → DESP | Payment instruction with funding part | [03-desp-post-payment-instructions.json](03-desp-post-payment-instructions.json) |
| 4 | DESP → PSP A | Received: payment and funding technically valid | [04-desp-response-201.json](04-desp-response-201.json) |
| 5 | DESP → DESP ledger | Settle: DCA A −30, Anna +30 −150, Clara +150 | [05-ledger-settlement.json](05-ledger-settlement.json) |
| 6 | DESP → PSP A | Final status: payment and funding settled | [06-psp-api-status-push.json](06-psp-api-status-push.json) |
| 7 | PSP A → DESP | Status received | [07-psp-api-204.json](07-psp-api-204.json) |
| 8 | PSP A → PSP A core banking | Debit 30.00 EUR from Anna's giro account | [08-giro-debit.json](08-giro-debit.json) |
| 9 | PSP A → Banking App A | Anna's app shows: paid, 30 EUR topped up from giro | [09-app-response.json](09-app-response.json) |

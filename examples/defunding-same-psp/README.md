# Ben takes 60 EUR back from digital euro to his giro account (defunding)

Manual defunding at the same bank (Annex D2-7 Fig. 3, D1-1 §7.1). The central platform redeems Ben's digital euro and credits central bank money back to PSP B's DCA; PSP B then credits Ben's giro account. From here on the money is ordinary bank money.

| Step | From → to | What | File |
|---|---|---|---|
| 0 | Banking App B → PSP B | Ben asks his bank to take back 60.00 EUR to his giro account | [00-app-defunding-request.json](00-app-defunding-request.json) |
| 1 | PSP B → DESP | Defunding instruction to the central platform | [01-desp-post-defundings.json](01-desp-post-defundings.json) |
| 2 | DESP → PSP B | Received and technically valid | [02-desp-response-201.json](02-desp-response-201.json) |
| 3 | DESP → DESP ledger | Settle: DCA B +60.00, Ben −60.00 | [03-ledger-settlement.json](03-ledger-settlement.json) |
| 4 | DESP → PSP B | Final status: settled | [04-psp-api-defunding-status-push.json](04-psp-api-defunding-status-push.json) |
| 5 | PSP B → DESP | Status received | [05-psp-api-204.json](05-psp-api-204.json) |
| 6 | PSP B → PSP B core banking | Credit 60.00 EUR to Ben's giro account | [06-giro-credit.json](06-giro-credit.json) |
| 7 | PSP B → Banking App B | Ben's app shows the new balances | [07-app-response.json](07-app-response.json) |

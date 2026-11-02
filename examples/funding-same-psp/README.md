# Clara moves 200 EUR from her giro account into digital euro (funding)

Manual funding at the same bank (Annex D2-7 Fig. 1, D1-1 §7.1). PSP A blocks the amount on Clara's giro account, the central platform issues new digital euro against PSP A's central bank money account (DCA), and PSP A then debits the giro account.

| Step | From → to | What | File |
|---|---|---|---|
| 0 | Banking App A → PSP A | Clara asks her bank to move 200.00 EUR into digital euro | [00-app-funding-request.json](00-app-funding-request.json) |
| 1 | PSP A → PSP A core banking | Block 200.00 EUR on Clara's giro account | [01-giro-block.json](01-giro-block.json) |
| 2 | PSP A → DESP | Funding instruction to the central platform | [02-desp-post-fundings.json](02-desp-post-fundings.json) |
| 3 | DESP → PSP A | Received and technically valid | [03-desp-response-201.json](03-desp-response-201.json) |
| 4 | DESP → DESP ledger | Settle: DCA A −200.00, Clara +200.00 | [04-ledger-settlement.json](04-ledger-settlement.json) |
| 5 | DESP → PSP A | Final status: settled | [05-psp-api-funding-status-push.json](05-psp-api-funding-status-push.json) |
| 6 | PSP A → DESP | Status received | [06-psp-api-204.json](06-psp-api-204.json) |
| 7 | PSP A → PSP A core banking | Debit 200.00 EUR from Clara's giro account | [07-giro-debit.json](07-giro-debit.json) |
| 8 | PSP A → Banking App A | Clara's app shows the new balances | [08-app-response.json](08-app-response.json) |

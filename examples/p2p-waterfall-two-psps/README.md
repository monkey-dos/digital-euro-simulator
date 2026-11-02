# Anna (PSP A) pays Ben (PSP B) 50 EUR; Ben's holding limit is 100 EUR (waterfall)

The game master lowers the holding limit to 100 EUR so the waterfall becomes visible. Ben has 80 EUR, so receiving 50 would take him to 130. PSP B answers the forwarded instruction with a defunding part of 30 EUR (D2-7 PSP API POST /payment-instructions response, p.104–105); the platform settles payment and defunding together, and PSP B credits the 30 EUR to Ben's giro account.

| Step | From → to | What | File |
|---|---|---|---|
| 0 | Game Master → all apps | Game master sets the holding limit to 100 EUR *(placeholder)* | [00-game-master-holding-limit.json](00-game-master-holding-limit.json) |
| 1 | Banking App A → PSP A | Anna asks her bank to pay Ben 50.00 EUR | [01-app-payment-initiation.json](01-app-payment-initiation.json) |
| 2 | PSP A → DESP | Which bank serves +4915100000003? *(placeholder)* | [02-alias-lookup.json](02-alias-lookup.json) |
| 3 | PSP A → DESP | Payment instruction to the central platform | [03-desp-post-payment-instructions.json](03-desp-post-payment-instructions.json) |
| 4 | DESP → PSP A | Received and technically valid | [04-desp-response-201.json](04-desp-response-201.json) |
| 5 | DESP → PSP B | Forwarded to Ben's bank | [05-psp-api-forward-to-payee-bank.json](05-psp-api-forward-to-payee-bank.json) |
| 6 | PSP B → DESP | PSP B accepts and asks to sweep 30.00 EUR to Ben's giro account | [06-psp-api-response-201-with-defunding.json](06-psp-api-response-201-with-defunding.json) |
| 7 | DESP → DESP ledger | Settle: Anna −50, Ben +50 −30.00, DCA B +30.00 | [07-ledger-settlement.json](07-ledger-settlement.json) |
| 8 | DESP → PSP A | Final status to PSP A: settled | [08-psp-api-status-push-payer-bank.json](08-psp-api-status-push-payer-bank.json) |
| 9 | PSP A → DESP | Status received | [09-psp-api-204-psp-a.json](09-psp-api-204-psp-a.json) |
| 10 | DESP → PSP B | Final status to PSP B: settled (incl. defunding) | [10-psp-api-status-push-payee-bank.json](10-psp-api-status-push-payee-bank.json) |
| 11 | PSP B → DESP | Status received | [11-psp-api-204-psp-b.json](11-psp-api-204-psp-b.json) |
| 12 | PSP B → PSP B core banking | Credit 30.00 EUR to Ben's giro account | [12-giro-credit.json](12-giro-credit.json) |
| 13 | PSP A → Banking App A | Anna's app shows: paid | [13-app-response.json](13-app-response.json) |

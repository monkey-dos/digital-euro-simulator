# Anna (PSP A) pays Ben (PSP B) 50 EUR; Ben's holding limit is 100 EUR (waterfall)

The game master lowers the holding limit to 100 EUR so the waterfall becomes visible. Ben has 80 EUR, so receiving 50 would take him to 130. PSP B answers the forwarded instruction with a defunding part of 30 EUR (D2-7 PSP API POST /payment-instructions response, p.104–105); the platform settles payment and defunding together, and PSP B credits the 30 EUR to Ben's giro account.

| Step | From → to | What | File |
|---|---|---|---|
| 0 | Game Master → all apps | Game master sets the holding limit to 100 EUR *(placeholder)* | [00-game-master-holding-limit.json](00-game-master-holding-limit.json) |
| 1 | Banking App A → PSP A | Anna asks her bank to pay Ben 50.00 EUR | [01-app-payment-initiation.json](01-app-payment-initiation.json) |
| 2 | PSP A → DESP | Which bank serves +4915100000003? *(placeholder)* | [02-alias-lookup-request.json](02-alias-lookup-request.json) |
| 3 | DESP → PSP A | Ben's DEAN, served by PSP B *(placeholder)* | [03-alias-lookup-response-200.json](03-alias-lookup-response-200.json) |
| 4 | PSP A → DESP | Payment instruction to the central platform | [04-desp-post-payment-instructions.json](04-desp-post-payment-instructions.json) |
| 5 | DESP → PSP A | Received and technically valid | [05-desp-response-201.json](05-desp-response-201.json) |
| 6 | DESP → PSP B | Forwarded to Ben's bank | [06-psp-api-forward-to-payee-bank.json](06-psp-api-forward-to-payee-bank.json) |
| 7 | PSP B → DESP | PSP B accepts and asks to sweep 30.00 EUR to Ben's giro account | [07-psp-api-response-201-with-defunding.json](07-psp-api-response-201-with-defunding.json) |
| 8 | DESP → DESP ledger | Settle: Anna −50, Ben +50 −30.00, DCA B +30.00 | [08-ledger-settlement.json](08-ledger-settlement.json) |
| 9 | DESP → PSP A | Final status to PSP A: settled | [09-psp-api-status-push-payer-bank.json](09-psp-api-status-push-payer-bank.json) |
| 10 | PSP A → DESP | Status received | [10-psp-api-204-psp-a.json](10-psp-api-204-psp-a.json) |
| 11 | DESP → PSP B | Final status to PSP B: settled (incl. defunding) | [11-psp-api-status-push-payee-bank.json](11-psp-api-status-push-payee-bank.json) |
| 12 | PSP B → DESP | Status received | [12-psp-api-204-psp-b.json](12-psp-api-204-psp-b.json) |
| 13 | PSP B → PSP B core banking | Credit 30.00 EUR to Ben's giro account | [13-giro-credit.json](13-giro-credit.json) |
| 14 | PSP A → Banking App A | Anna's app shows: paid | [14-app-response.json](14-app-response.json) |

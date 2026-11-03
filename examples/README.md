# Example message sequences

Each folder is one scenario, one file per step, numbered in the order the messages travel. The observer will later play these steps one by one.

| Scenario | What it shows |
|---|---|
| [p2p-same-psp](p2p-same-psp/) | Anna pays Clara 25 EUR. Both at PSP A, so the central platform settles directly and never sees a name. |
| [p2p-two-psps](p2p-two-psps/) | Anna (PSP A) pays Ben (PSP B) 50 EUR. The platform forwards the instruction, PSP B adds Ben's ledger entry, and both banks get the final status. |
| [p2p-reverse-waterfall-same-psp](p2p-reverse-waterfall-same-psp/) | Anna pays Clara 150 EUR with only 120 EUR on her account; 30 EUR come from her giro account in the same atomic step (reverse waterfall). |
| [funding-same-psp](funding-same-psp/) | Clara moves 200 EUR from her giro account into digital euro (funding). New digital euro are issued against PSP A's DCA. |
| [defunding-same-psp](defunding-same-psp/) | Ben takes 60 EUR back to his giro account (defunding). PSP B's DCA gets the central bank money back. |
| [p2p-waterfall-two-psps](p2p-waterfall-two-psps/) | Anna pays Ben 50 EUR, but the game master has set the holding limit to 100 EUR; 30 EUR are swept to Ben's giro account in the same step (waterfall). |

Test persons, banks and starting balances: [test-data.json](test-data.json). All fictional.

## File format

```jsonc
{
  "step": 2,                     // order in the sequence
  "title": "…",                  // plain-language headline for the observer
  "from": "PSP A", "to": "DESP",
  "interface": "I3",
  "specRef": "Annex D2-7 p.57–62",
  "schema": "contracts/…",       // the body must validate against this
  "placeholder": true,           // only if the spec doesn't define this step
  "http": { "method": "POST", "path": "/v1/…", "headers": { … } },   // or { "status": 201, … }
  "body": { … },                 // exactly what goes over the wire
  "decryptedView": { … },        // only for the observer: content of an encrypted field
  "explanation": "…"
}
```

Every I1 request carries the placeholder header `Sim-User-DEAN` (who is logged in, INTERPRETATION A12). The alias lookup is a placeholder call (T5) shown as two steps: request and 200 response.

Regenerate with `python3 tools/generate_examples.py`, check with `python3 tools/validate.py`. `python3 tools/e2e_flows.py --start` plays the same flows live through the reference apps and checks that they send messages of the same shape.

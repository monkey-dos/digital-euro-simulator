# Example message sequences

Each folder is one scenario, one file per step, numbered in the order the messages travel. The observer will later play these steps one by one.

| Scenario | What it shows |
|---|---|
| [p2p-same-psp](p2p-same-psp/) | Anna pays Clara 25 EUR. Both at PSP A, so the central platform settles directly and never sees a name. |
| [p2p-two-psps](p2p-two-psps/) | Anna (PSP A) pays Ben (PSP B) 50 EUR. The platform forwards the instruction, PSP B adds Ben's ledger entry, and both banks get the final status. |
| [p2p-reverse-waterfall-same-psp](p2p-reverse-waterfall-same-psp/) | Anna pays Clara 150 EUR with only 120 EUR on her account; 30 EUR come from her giro account in the same atomic step. |

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

Regenerate with `python3 tools/generate_examples.py`, check with `python3 tools/validate.py`.

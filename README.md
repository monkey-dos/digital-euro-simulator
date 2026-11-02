# Digital Euro Simulator

An educational simulation of the ECB **digital euro**. It shows what happens between the central platform (DESP), banks (PSPs), banking apps and, later, merchants when people pay each other in digital euro. Every message follows the ECB's published specification where one exists.

> **No real money. Not an implementation.** This project is a teaching tool. It is based on the *draft* digital euro scheme rulebook v0.91 (July 2026) and its annexes, which the ECB explicitly marks as not intended as a basis for implementation. Everything here is fictional: banks, people, account numbers.

## What it will look like

- A **banking app** for each bank. Test users open a digital euro account, fund it from their giro account, and pay each other.
- The **central platform (DESP)** keeps the one ledger where all digital euro live.
- At least **two banks (PSPs)**, each built as its own app. A bank provides only the interface; the money itself sits on the ECB ledger.
- A **transparency observer** shows every message travelling between the apps, slowed down so you can follow it, plus all balances in real time.
- A **game master** controls speed, prepares scenarios and can top up accounts that run dry. That creates money, which is impossible in reality, so every top-up is labelled.
- Later: a **merchant gateway** with a test shop.

See [the component map](docs/architecture/component-map.md) for all parts and interfaces.

## How the repository is organised

| Folder | What's in it |
|---|---|
| `contracts/` | The interfaces between apps: JSON schemas and the rules we chose where the spec is open. **Start here if you want to build an app.** |
| `examples/` | Complete example message sequences, step by step, built according to the spec. |
| `apps/` | One folder per app. Each app is developed independently and talks to others only through `contracts/`. |
| `docs/` | Architecture, decisions (ADRs), reading notes on the ECB documents. |
| `tools/` | Scripts that generate and validate the examples. |

## The interfaces

| # | Between | Basis |
|---|---|---|
| I1 | Banking app ↔ its bank | ECB Annex D1-1 |
| I2 | Merchant system ↔ gateway ↔ acquiring bank | partly spec (phase 2) |
| I3 | Bank ↔ central platform (DESP), both directions | ECB Annex D2-7, D2-1, D2-6, D2-8 |
| I4 | Central platform ↔ central bank money accounts (DCA) | simplified |
| I5 | Bank back-end ↔ its giro account system | ours |
| I6 | All apps → network relay → observer | ours |
| I7 | Game master → all apps | ours |

Two apps that respect the same contract can replace each other. For example, a bank can choose a different banking app.

## Build phases

1. **Money between people:** open an account, register a phone alias, funding and defunding, pay at the same bank and across banks, waterfall and reverse waterfall, observer with slow motion.
2. **Merchants:** business accounts, QR payments in a shop, pay-by-link, refunds, pre-authorisation.
3. **Scheme depth:** fraud scoring, disputes, reports, switching banks, standing orders, offline.

## Try the examples

**Watch them:** open `apps/observer/index.html` in a browser. The observer plays every example step by step, with live balances.

**Check them:**

```bash
pip install jsonschema
python3 tools/generate_examples.py   # rebuilds examples/ from the test data
python3 tools/validate.py            # checks every example against the schemas
python3 tools/build_observer.py      # bundles the examples for the observer
```

## Sources

ECB, digital euro scheme rulebook v0.91 and annexes (draft, 2 July 2026), published at ecb.europa.eu. Reading notes are in `docs/spec-notes/`; always check against the original before relying on a field name.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Code and documentation in this repository: [MIT](LICENSE). The ECB documents themselves are not part of this repository and are not covered by this license; short references and field names are quoted for explanation.

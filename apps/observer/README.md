# Transparency observer

**Run by:** simulation layer (not part of the real scheme)

Plays the example message sequences from `/examples` step by step: each message travels visibly between the apps, the inspector shows the exact message (headers, body, encrypted part), and the balances of the ECB ledger, the banks' central bank money accounts (DCA) and the giro accounts change live.

## Open it

- **Quickest:** open `apps/observer/index.html` in a browser (double-click). It reads the bundled data from `scenarios.js` next to it.
- **Single file:** `apps/observer/dist/observer.html` contains everything in one file, e.g. to send to someone.

After changing examples, rebuild the data:

```bash
python3 tools/generate_examples.py   # rebuild examples/
python3 tools/build_observer.py      # bundle them for the observer
```

## What it shows

- **Speed:** 0.5–5 seconds per message, pause, single step, jump to any step.
- **Whose view:** everything (game master, default, see ADR 0003) · what the central platform sees (no names, encrypted parts closed, giro accounts hidden) · what PSP A or PSP B sees (only its own messages and customers) · what the public sees (totals only).
- **Bookkeeping check:** the change of digital euro in circulation must mirror the change of the banks' DCAs (plus any game-master top-ups, ADR 0002).

## Next

Today it replays recorded examples (offline). Later it will receive the same message format live from the network relay (interface I6).

# Control room ("Banana Ledger")

**Run by:** simulation layer (not part of the real scheme)

The browser page of the simulator. It shows every message between the apps as it travels, explains each step in plain English, and shows how the money changes. One self-contained file (`index.html`, no build step, no frameworks; only the fonts come from Google Fonts, with system fallbacks).

## Open it

- **Live (the real simulation):** start everything with `python3 tools/run_local.py --control-room` and open <http://127.0.0.1:8100/>. The network relay serves the page and its feed (interfaces I6 and I7).
- **Live, page opened from a file:** `index.html?relay=http://127.0.0.1:8100`.
- **Offline replay:** open `index.html` directly (double-click) or `dist/observer.html` (a single file with the recorded examples inlined, e.g. to send around or publish). It then replays the examples from `/examples` with play, pause, step and back. A banner says so.

After changing the examples, rebuild the recorded data:

```bash
python3 tools/generate_examples.py   # rebuild examples/
python3 tools/build_observer.py      # bundle them (scenarios.js and dist/observer.html)
```

`build_observer.py` replaces the tag `<script src="scenarios.js"></script>` in `index.html`; keep that tag.

## What each part shows

- **Header:** logo, the **Map | Timeline** switch (your choice is remembered), the scenario picker with **Run scenario** (live: the example flows from the relay plus *Custom…* for a free pay / fund / defund action; offline: the recorded examples), and connection dots (green = the app answers, red = it does not).
- **Control bar:** back to start (live: reset, after a confirmation), step back, play / pause, step forward, speed (0–5 s per message), **Whose view**, the violet **Helicopter Money** button (money creation, ADR 0009; live only, disabled with a tooltip in the offline replay) and *Settings* (holding limit of all banks, live only).
  - Live, **pause** mode: every message waits at the gate until you press step forward. **Play** lets each message wait the chosen number of seconds. Several waiting messages are released oldest first.
  - Step back or clicking an earlier step only *reviews* it; the live run carries on in the background. **Back to live** returns.
- **Map:** the apps as a map (banking app A, PSP A, central platform with its ledger card, PSP B, banking app B). The travelling pill shows the step number, a short label and a lock when the message has a sealed (`SIMENC`) part. Below it: the narration, then the step chips (done, now, waiting, upcoming steps of the running example).
- **Inspector (right of the map):** route, interface and spec reference, who can read what, headers, the body as sent (sealed parts shortened), and the sealed part opened for the simulation.
- **Money row:** digital euro in circulation, one tile per person (digital euro and giro account; a small violet "X created" pill once the person received Helicopter Money), the banks' central bank accounts (DCA), the bookkeeping check and the **Helicopter Money** tile ("newly created, impossible in reality", with "digital euro X · giro Y (via central bank accounts)"). The check stays *Balanced* and its caption says Helicopter Money is included; it shows *Out of balance* if the DESP's money check fails or, for a bank, the central bank money the DESP created on its DCA differs from the giro Helicopter Money the bank credited.
- **Timeline:** a swimlane sequence diagram, one row per message (past grey, current blue dashed, waiting dotted blue, upcoming dotted grey); settlements and giro steps are boxes on their column. Click a row to select it. The side panel has the narration, buttons for the full message and the sealed part, the money list and *Whose view*.
- **Whose view:** *Everything* (game master) · *Central platform* (no names, cannot open sealed parts, no giro accounts; sees the entry and DCA bookings of Helicopter Money) · *PSP A* / *PSP B* (only its own messages and customers, can open sealed parts addressed to it; sees only its own bank ledger) · *Public* (totals only, including the Helicopter Money total).

## Helicopter Money (the agreed look, "Version B")

Live only. The violet tokens (`--violet`, `--violet-t`, `--violet-l`) and the tile `.gm` mark everything the game master creates.

1. The **Helicopter Money** button (small stroke helicopter icon) switches on *Helicopter Money mode*: the button turns solid violet and reads **Done adding money**; a violet banner above the money row says: "Helicopter Money. Pick a person below and drop new money on their digital euro or giro account. Impossible with the real digital euro, so every drop is counted separately." Escape or *Done adding money* leaves the mode.
2. In the mode every **person** tile gets a dashed violet **+ Add money** button (DCA tiles get none; their caption gains "grows with giro Helicopter Money"). Clicking it expands that tile (only one is open at a time): a *Digital euro | Giro* toggle, quick chips +50 / +100 / +500, an amount field with a label, the hint "Room up to the limit: X €" (digital euro only) and a solid violet **Create 100.00 €** button (the amount follows the field). An error from the relay (for example the holding limit) shows inline in the tile and as a toast. All controls are real buttons, labels and inputs, reachable with the keyboard, at least 44 px high.
3. **Map:** once Helicopter Money messages exist, a dashed violet **Game master** node ("Simulation only – not part of the digital euro") appears below the central platform with dashed violet wires to the DESP and to the banks; the travelling message pills are violet. The DESP ledger card shows the changed line in violet. For giro money the bank card gets a small "BANK LEDGER · HELICOPTER MONEY" section: "DCA at the central bank +X" and "giro of <name> +X".
4. **Narration** for these steps is violet and in plain English (for example "Helicopter Money: 100.00 € digital euro for Anna – The central platform adds 100.00 € to Anna's digital euro entry. No bank pays for it …"). The step chips are violet and carry a "game master" label.
5. **Timeline:** a violet *Game master* lane appears in front of the others only while game-master messages exist.

Everything optional is wrapped so that a missing field (for example an app without Helicopter Money data) shows 0 instead of breaking the page.

## How live data becomes steps

The page reads `GET /control/history`, then follows `GET /control/events?since=<seq>` (see `contracts/i6-observer-events`) and reconnects by itself. Messages, ledger bookings, giro steps and notes become one list of steps. While an example runs, each live step is matched to the next unused step of that example (same sender and receiver, same method and path pattern, same status) to reuse its title, explanation and spec reference; everything else, such as free actions, gets an automatic plain-English description. Commands go to the relay (`contracts/i7-game-master`). A new run starts a fresh timeline; reset clears it.

If the relay or `scenarios.js` is missing the page does not break: it falls back to the replay or shows an empty state.

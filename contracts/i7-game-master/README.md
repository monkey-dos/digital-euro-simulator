# I7 – Game master commands (ours, simulation only)

Status: **v0.1**, implemented by `apps/network-relay` (control room) and the apps' `/sim/…` endpoints. Not part of the ECB scheme.

All commands are JSON `POST`s to the relay (default `http://127.0.0.1:8100`). Answers are `{"ok": true, …}` or `{"ok": false, "error": "…"}` with HTTP 400/404/409.

| Command | Body | Effect |
|---|---|---|
| `POST /control/mode` | `{"mode": "play"}` or `{"mode": "pause"}` | play: every message waits `delaySeconds`, one after the other. pause: messages wait for a step |
| `POST /control/delay` | `{"seconds": 1.5}` (0–60) | slow-motion speed; 0 = no waiting |
| `POST /control/step` | – | pause mode only (409 otherwise): lets exactly one waiting message continue (the oldest); `ok: false` with `error` "Nothing is waiting" if none waits |
| `POST /control/reset` | – | every app back to the test data (`POST /sim/reset` on each); refused (409) while a scenario is running or a message is still waiting |
| `POST /control/holding-limit` | `{"amount": "100.00"}` (0–1,000,000, at most two decimals) | sets the holding limit at every bank (`SET_HOLDING_LIMIT`, ADR 0005); `ok: false` if a bank refused; refused (409) while a scenario runs |
| `POST /control/helicopter-money` | `{"person": "anna", "account": "digital-euro", "amount": "100.00"}`; `account` is `"digital-euro"` or `"giro"` | **Helicopter Money** (money creation, ADR 0002). Answers `202` with `{"ok": true, "started": "…", "helicopterId": "HM-…"}`; progress and the result arrive in the feed (I6). Errors as `{"ok": false, "error": "…"}`: 400 bad amount (not positive, more than two decimals, above 1,000,000.00, not a number) or unknown account, 404 unknown person, 409 while a scenario or another drop is running or a message waits at the gate, 409 if a digital euro drop would take the person above the holding limit (bank's view: digital euro balance + pending incoming + amount), 502 if the bank does not answer so the limit cannot be checked |
| `GET /control/scenarios` | – | `{"examples": [{"id", "title"}], "people": [{"id", "name", "bank"}], "actions": ["pay", "fund", "defund"]}` |
| `POST /control/scenarios/<id>` | – | plays an example flow from `/examples`: the relay sends the example's first banking-app message with fresh IDs and timestamps; a holding limit the example sets is put back afterwards to what the game master had set before |
| `POST /control/actions` | `{"action": "pay", "payer": "anna", "payee": "ben", "amount": "50.00", "text": "Pizza"}`; `fund` / `defund` need only `payer` and `amount` | a free action, built from the example messages with these values |

### Helicopter Money in detail

The relay is the game master and orchestrates a drop. It sends its messages **through the gate** (slow motion, pause and step apply); they appear in the feed as messages `from: "Game master"` (`fromId: "game-master"`) on interface `sim (not ECB)`. After the first message it waits for the answer before sending the next.

| Kind | 1st message (relay → DESP) | 2nd message (relay → the person's bank) |
|---|---|---|
| `digital-euro` | `POST /sim/helicopter-money` `{"target": "entry", "entryId": "…", "amount": "100.00", "helicopterId": "HM-…"}`: new digital euro on the person's ledger entry | `POST /sim/helicopter-money` `{"account": "digital-euro", "dean": "…", "amount": "100.00", "helicopterId": "HM-…"}`: the bank updates its copy of the balance |
| `giro` | `{"target": "dca", "bic": "…", "amount": "100.00", "helicopterId": "HM-…"}`: new central bank money on the bank's DCA | `{"account": "giro", "dean": "…", "amount": "100.00", "helicopterId": "HM-…"}`: the bank books "DCA at the central bank +X / giro of the person +X" and credits the giro account |

The relay validates what it can before the first call (person, amount, holding limit from the bank's `GET /sim/state`). If the bank still refuses, the relay sends `{"reverse": "<helicopterId>"}` to the DESP, so the books never stay unbalanced, and reports the error (`scenario` event with `status: "failed"`). All answers are `{"ok": true, …}` or `{"ok": false, "error": "…"}` with 400, 404 or 409. These `/sim/…` endpoints are simulation only, not part of the ECB scheme; each app logs its own booking (DESP: a `ledger` step, bank: a `bank-ledger` step and a giro step) so the feed shows them (I6).

Totals are in `GET /sim/state`: DESP `helicopterMoney: {"digitalEuro": "…", "dca": {"<BIC>": "…"}}` and `moneyCheck.ok`; each bank `helicopterMoney: {"giro", "digitalEuro", "dcaReceived", "ok", "bookings": [...]}`. A reset (`/sim/reset` on every app) sets them back to 0.

Scenarios answer `202` at once; progress and the result arrive in the feed (I6, `scenario` events). Only one scenario runs at a time: starting another one (or a Helicopter Money drop) while it runs is refused with 409.

The relay plays the banking app until real banking apps exist. Every message it sends that way is marked `standIn: true` in the feed.

## Not yet built

- Creating test users (depends on account opening, still a placeholder in the ECB documents we have).

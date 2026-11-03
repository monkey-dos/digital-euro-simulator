# I7 – Game master commands (ours, simulation only)

Status: **v0.1**, implemented by `apps/network-relay` (control room) and the apps' `/sim/…` endpoints. Not part of the ECB scheme.

All commands are JSON `POST`s to the relay (default `http://127.0.0.1:8100`). Answers are `{"ok": true, …}` or `{"ok": false, "error": "…"}` with HTTP 400/404/409.

| Command | Body | Effect |
|---|---|---|
| `POST /control/mode` | `{"mode": "play"}` or `{"mode": "pause"}` | play: every message waits `delaySeconds`, one after the other. pause: messages wait for a step |
| `POST /control/delay` | `{"seconds": 1.5}` (0–60) | slow-motion speed; 0 = no waiting |
| `POST /control/step` | – | pause mode only: lets exactly one waiting message continue (the oldest) |
| `POST /control/reset` | – | every app back to the test data (`POST /sim/reset` on each); refused (409) while a scenario is running |
| `POST /control/holding-limit` | `{"amount": "100.00"}` | sets the holding limit at every bank (`SET_HOLDING_LIMIT`, ADR 0005) |
| `GET /control/scenarios` | – | `{"examples": [{"id", "title"}], "people": [{"id", "name", "bank"}], "actions": ["pay", "fund", "defund"]}` |
| `POST /control/scenarios/<id>` | – | plays an example flow from `/examples`: the relay sends the example's first banking-app message with fresh IDs and timestamps; a holding limit the example sets is restored afterwards |
| `POST /control/actions` | `{"action": "pay", "payer": "anna", "payee": "ben", "amount": "50.00", "text": "Pizza"}`; `fund` / `defund` need only `payer` and `amount` | a free action, built from the example messages with these values |

Scenarios answer `202` at once; progress and the result arrive in the feed (I6, `scenario` events).

The relay plays the banking app until real banking apps exist. Every message it sends that way is marked `standIn: true` in the feed.

## Not yet built

- Top-ups by the game master (money creation, ADR 0002): planned as `POST /control/top-up` with a `MONEY_CREATED` event, needs a matching command in the DESP and the banks.
- Creating test users (depends on account opening, still a placeholder in the ECB documents we have).

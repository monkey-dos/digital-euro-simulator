# I6 – Control room feed (ours, simulation only)

Status: **v0.1**, implemented by `apps/network-relay`. Not part of the ECB scheme.

The network relay sees every message between the apps (it forwards them) and also reads the steps that happen inside an app (DESP ledger booking, a bank's giro block). It publishes all of it as one numbered list of events.

## Reading the feed

| Call | Answer |
|---|---|
| `GET /control/history?since=<seq>` | `{"events": [...], "control": {...}, "apps": {...}}`: events with a number above `since` (0 = all kept so far), the gate's current status and the apps known to the relay |
| `GET /control/events?since=<seq>` | The same events live, as [server-sent events](https://html.spec.whatwg.org/multipage/server-sent-events.html): one `data:` line with one JSON event each; `id:` is the event's `seq` |
| `GET /control/state` | Fetches the balances now and returns the latest `state` event |

The control room reads `history` once, then follows `events?since=<last seq>`. A `reset` event means everything before it no longer applies.

## Event envelope

Every event has `seq` (1, 2, 3 …, gaps possible after a reset), `type` and `time` (UTC, set by the relay). The other fields depend on `type`.

### `message` – a message reached the relay and is now waiting at the gate

| Field | Meaning |
|---|---|
| `id` | `m1`, `m2` … unique per relay run |
| `kind` | `request` or `response` |
| `inReplyTo` | for a response: the `id` of its request |
| `from`, `to` | display names (`Banking App A`, `PSP A`, `DESP`, …), the same names the apps use in their own logs |
| `fromId`, `toId` | relay names (`app-a`, `psp-a`, `desp`, …) |
| `interface` | `I1`, `I3`, `I3 (placeholder)` or `sim (not ECB)` |
| `method`, `path` | request line; a response repeats the request's `path` and has `method: null` |
| `status` | HTTP status of a response, otherwise absent |
| `headers` | the technical headers defined in the contracts (INTERPRETATION T1, A12) |
| `body` | the JSON body exactly as sent; encrypted parts stay `SIMENC:…` (INTERPRETATION C7) |
| `standIn` | `true` when the relay itself played the banking app (no real app exists yet) |

### `released` – the gate let message `id` continue

`{"id": "m4"}`. Until then the message is "on its way".

### `internal` – a step inside one app (no network message)

| Field | Meaning |
|---|---|
| `app`, `appId` | which app reported it |
| `kind` | `ledger` (DESP booking), `giro` (bank's core banking: block, debit, credit, release), `note` (anything else, e.g. a rejection reason) |
| `from`, `to`, `interface`, `body`, `note` | as in the app's own log (`GET /sim/events`); `body` of a ledger booking has `UETR`, `settlementDateTime`, `bookings[]` (`entry`, `before`, `change`, `after`), the same shape as `examples/*-ledger-settlement.json` |
| `appTime` | when the app logged it |

### `state` – balances changed

`{"apps": {"desp": <DESP GET /sim/state>, "psp-a": <PSP A GET /sim/state>, "psp-b": …}}`. An app that did not answer is `null`. Sent only when something changed.

### `control` – the gate changed

`{"mode": "play"|"pause", "delaySeconds": 1.5, "waiting": 2, "next": "m7"}`; after a game master command also `gameMaster` (text) and, for the holding limit, `holdingLimit`.

### `scenario` – the game master started a scenario

| `status` | Fields |
|---|---|
| `started` | `id`, `title`, `steps` (the example's steps for the narration: `step`, `title`, `from`, `to`, `interface`, `method`, `path`, `status`, `placeholder`, `specRef`, `explanation`; empty for a free action), `standIn: true` |
| `finished` | `id`, `title`, `ok` (the bank answered `ReturnCode` 0), `httpStatus`, `answer` (the bank's I1 answer) |
| `failed` | `id`, `title`, `ok: false`, `error` |

### `error` – the relay could not reach an app

`{"id": "m5", "text": "DESP did not answer: ConnectError"}`. The caller then gets HTTP 502 with problem+json and `reasonCode` `XNET` (the code a bank uses for "central platform not reachable").

### `reset`

`{"results": {"DESP": true, "PSP A": true, "PSP B": true}}`: all apps are back at the test data.

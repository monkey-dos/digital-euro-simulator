# Network relay

**Run by:** simulation layer (not part of the ECB scheme)

**Does:** All traffic between the apps passes through it. Every request and every response waits at a gate, so the control room can show it in slow motion or step by step. The relay never changes a message. It also serves the control room page (`apps/observer`) and its live feed.

**Offers interfaces:** the relay route for I1 and I3, the control room feed (I6), game master commands (I7)

**Uses interfaces:** I1 and I3 (passes them on), the apps' `/sim/…` endpoints (balances, inside-the-app steps, reset, holding limit)

## Start

```bash
python3 tools/run_local.py --control-room          # slow motion, 1.5 s per message
python3 tools/run_local.py --control-room --pause  # starts paused: step by step
```

Then open http://127.0.0.1:8100 in a browser.

## How the apps reach each other

An app that wants to call another one uses the address

```
http://127.0.0.1:8100/r/<from>/<to>/<path>
```

for example PSP A calls the DESP at `http://127.0.0.1:8100/r/psp-a/desp/v1/payment-instructions`. The relay forwards to the address of `<to>` in `config/relay.json` and returns the answer. `run_local.py --control-room` gives every app these addresses (PSP: `DESP_URL`; DESP: a generated participant register), so the apps' code stays unchanged.

Names: `app-a`, `app-b` (banking apps), `psp-a`, `psp-b`, `desp`, and `game-master` (the relay itself as sender of Helicopter Money messages; it has no address).

## The gate

- **play:** each message waits the set time (0–60 s), one after the other, oldest first.
- **pause:** messages wait until the game master clicks "step"; each step lets exactly one through.

One scenario runs at a time. Reset is refused while a scenario runs or a message is still waiting, so old messages never reach freshly reset apps.

Because a paused message can wait a long time, `--control-room` raises the apps' waiting times to one hour.

If the relay cannot reach an app, it answers the caller with HTTP 502, problem+json and reason code `XNET`, as if the network had failed.

## Banking app stand-in

There is no banking app yet. When the game master starts a scenario, the relay sends the banking app's message itself (marked `standIn: true` in the feed). Real banking apps can replace it later by sending to `/r/app-a/psp-a/i1/messages`.

## Game master: Helicopter Money

`POST /control/helicopter-money` (I7, ADR 0009) makes the relay the game master. It checks the input and the holding limit, answers 202, then sends its own messages **through the gate** (so slow motion, pause and step apply, and they show in the feed from `Game master`): to the DESP (new digital euro on the person's entry, or new central bank money on the bank's DCA), then to the person's bank (update the balance copy, or book and credit giro money). If the bank refuses after the DESP booked, the relay sends an undo to the DESP; after an error or a lost answer (5xx, 502, timeout) it sends the undo to the DESP and the bank, because it cannot know what was booked ("nothing to undo", 404, is fine). Refused (409) while a scenario runs, another drop runs or a message waits, like reset; the slot is claimed before the first wait, so two drops at the same moment cannot both start. The apps' `/sim/…` endpoints are for the relay only: the relay route `/r/<from>/<to>/…` answers 403 (problem+json) for any path starting with `/sim/` and for `game-master` as sender.

## Settings

`config/relay.json`, or environment variables: `RELAY_MODE` (`play`/`pause`), `RELAY_DELAY` (seconds), `RELAY_APP_URLS` (JSON `{"desp": "http://…"}`), `RELAY_FORWARD_TIMEOUT`, `RELAY_PORT`. The start and test scripts in `tools/` expect the relay on port 8100.

The relay listens only on your own computer (127.0.0.1). Its control commands accept calls from any web page open in your browser (so the control room also works when opened as a file); with fictional data that is acceptable, but do not run it on a shared server.

Contracts: [`contracts/i6-observer-events`](../../contracts/i6-observer-events/README.md), [`contracts/i7-game-master`](../../contracts/i7-game-master/README.md).

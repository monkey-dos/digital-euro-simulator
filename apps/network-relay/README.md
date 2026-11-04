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

Names: `app-a`, `app-b` (banking apps), `psp-a`, `psp-b`, `desp`.

## The gate

- **play:** each message waits the set time (0–60 s), one after the other, oldest first.
- **pause:** messages wait until the game master clicks "step"; each step lets exactly one through.

One scenario runs at a time. Reset is refused while a scenario runs or a message is still waiting, so old messages never reach freshly reset apps.

Because a paused message can wait a long time, `--control-room` raises the apps' waiting times to one hour.

If the relay cannot reach an app, it answers the caller with HTTP 502, problem+json and reason code `XNET`, as if the network had failed.

## Banking app stand-in

There is no banking app yet. When the game master starts a scenario, the relay sends the banking app's message itself (marked `standIn: true` in the feed). Real banking apps can replace it later by sending to `/r/app-a/psp-a/i1/messages`.

## Settings

`config/relay.json`, or environment variables: `RELAY_MODE` (`play`/`pause`), `RELAY_DELAY` (seconds), `RELAY_APP_URLS` (JSON `{"desp": "http://…"}`), `RELAY_FORWARD_TIMEOUT`, `RELAY_PORT`. The start and test scripts in `tools/` expect the relay on port 8100.

The relay listens only on your own computer (127.0.0.1). Its control commands accept calls from any web page open in your browser (so the control room also works when opened as a file); with fictional data that is acceptable, but do not run it on a shared server.

Contracts: [`contracts/i6-observer-events`](../../contracts/i6-observer-events/README.md), [`contracts/i7-game-master`](../../contracts/i7-game-master/README.md).

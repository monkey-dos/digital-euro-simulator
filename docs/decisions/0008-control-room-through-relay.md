# ADR 0008: The control room watches the network relay; the relay stands in for the banking apps

Status: accepted (3 November 2026)

## Decision
1. All traffic between the apps passes through the network relay (`apps/network-relay`). Every request and every response waits at a gate: in play mode for a set time (slow motion), in pause mode until the game master presses "step". The relay never changes a message.
2. The control room (`apps/observer`, project name **Banana Ledger**) is served by the relay and reads one live feed (I6). Steps inside an app (DESP ledger booking, giro steps) come from the apps' existing logs (`GET /sim/events`), not from new code in the apps.
3. Until real banking apps exist, the relay plays them when the game master starts a scenario. Every such message is marked `standIn: true`.
4. The apps learn the relay's addresses from configuration only (`tools/run_local.py --control-room`), so they run unchanged with or without the relay.

## Why
The relay is the one place that sees every message, so the apps stay free of simulation code and can be swapped. Holding messages at a gate gives slow motion and step-by-step explaining without touching the payment logic. Reading the apps' logs keeps the inside-the-app steps visible with no new interface in the apps.

## Consequences
- While a message waits on pause, the apps wait too. `--control-room` raises their timeouts to one hour.
- If the relay cannot reach an app it answers 502 with reason code `XNET`, as if the network had failed.
- Helicopter Money (ADR 0009, which supersedes ADR 0002) is the one game-master command that makes the relay send its own messages (`from: Game master`) through the gate; the DESP and the banks only offer simulation-only `/sim/helicopter-money` endpoints. The control room's button, which was "coming later", is now "Helicopter Money" (live only).
- `tools/e2e_flows.py --via-relay` checks that every message arrives unchanged; `tools/relay_checks.py` checks pause, step, slow motion and the game master commands.

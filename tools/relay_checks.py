#!/usr/bin/env python3
"""Check the network relay and the game master commands (I6/I7) live.

    python3 tools/relay_checks.py --start     # starts the apps + relay, stops them afterwards
or, with  python3 tools/run_local.py --control-room  already running:
    python3 tools/relay_checks.py

Checks:
  1. pause: a started scenario stops at its first message; nothing reaches the bank;
  2. step: each step lets exactly one message through, oldest first, until the
     scenario finishes with ReturnCode 0; every message is released exactly once;
  3. reset and a second scenario are refused while a scenario runs; reset works afterwards;
  4. play with a delay: messages really wait (slow motion);
  5. free actions (pay, fund, defund) settle and change the balances as expected;
  6. inside-the-app steps (ledger booking, giro) appear in the feed, before the
     message that follows them;
  7. wrong input is refused with a clear error, and an unknown route gives 404.
Uses only the Python standard library. Exit code 0 only if everything passes.
"""
import argparse
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from decimal import Decimal

RELAY = "http://127.0.0.1:8100"


def http(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(RELAY + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw.decode(errors="replace")


def events(types=None):
    _, h = http("GET", "/control/history")
    return [e for e in h["events"] if types is None or e["type"] in types]


def wait_for(pred, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        v = pred()
        if v:
            return v
        time.sleep(0.1)
    return None


def finished():
    return next((e for e in events(["scenario"]) if e["status"] in ("finished", "failed")), None)


def balances():
    _, s = http("GET", "/control/state")
    out = {}
    for slug in ("psp-a", "psp-b"):
        for c in (s.get("apps", {}).get(slug) or {}).get("customers", []):
            out[c["name"].split()[0].lower()] = (Decimal(c["digitalEuro"]), Decimal(c["giro"]))
    return out


def fresh(mode="play", delay=0.0):
    http("POST", "/control/mode", {"mode": "play"})
    http("POST", "/control/delay", {"seconds": 0})
    wait_for(lambda: http("GET", "/control/history")[1]["control"]["waiting"] == 0, 5)
    status, r = http("POST", "/control/reset")
    if status != 200 or not r.get("ok"):
        raise SystemExit(f"Reset failed: {status} {r}")
    http("POST", "/control/delay", {"seconds": delay})
    http("POST", "/control/mode", {"mode": mode})


def check_pause_and_step():
    problems = []
    fresh("pause")
    before = balances()
    http("POST", "/control/scenarios/p2p-same-psp")
    first = wait_for(lambda: events(["message"]), 5)
    time.sleep(0.8)
    msgs = events(["message"])
    if len(msgs) != 1 or msgs[0]["path"] != "/i1/messages" or not msgs[0].get("standIn"):
        problems.append(f"paused: expected only the app's first message, got {[(m['from'], m['path']) for m in msgs]}")
    if events(["released"]):
        problems.append("paused: a message was released without a step")
    if balances() != before:
        problems.append("paused: balances changed although nothing was released")
    status, r = http("POST", "/control/reset")
    if status != 409:
        problems.append(f"reset during a running scenario: expected 409, got {status}")
    status, r = http("POST", "/control/scenarios/p2p-two-psps")
    if status != 409:
        problems.append(f"second scenario while one runs: expected 409, got {status}")
    steps = 0
    while not finished() and steps < 40:
        n_rel = len(events(["released"]))
        waiting = wait_for(lambda: http("GET", "/control/history")[1]["control"]["waiting"] or finished(), 5)
        if finished():
            break
        status, r = http("POST", "/control/step")
        steps += 1
        if status != 200 or not r.get("ok"):
            problems.append(f"step {steps}: {status} {r}")
            break
        if not wait_for(lambda: len(events(["released"])) == n_rel + 1, 5):
            problems.append(f"step {steps}: no message released")
            break
        time.sleep(0.15)
        if len(events(["released"])) != n_rel + 1:
            problems.append(f"step {steps}: more than one message released")
    done = wait_for(finished, 5)
    if not done or not done.get("ok"):
        problems.append(f"scenario did not finish ok: {done}")
    msg_ids = [m["id"] for m in events(["message"])]
    rel_ids = [m["id"] for m in events(["released"])]
    if sorted(msg_ids) != sorted(rel_ids) or len(set(rel_ids)) != len(rel_ids):
        problems.append(f"every message must be released exactly once: shown {msg_ids}, released {rel_ids}")
    if rel_ids != msg_ids:
        problems.append(f"released out of order: shown {msg_ids}, released {rel_ids}")
    if steps != len(msg_ids):
        problems.append(f"{steps} steps for {len(msg_ids)} messages")
    after = balances()
    if after.get("anna", (0,))[0] != before["anna"][0] - 25 or after.get("clara", (0,))[0] != before["clara"][0] + 25:
        problems.append(f"balances after Anna pays Clara 25: {after}")
    print(f"   pause/step: {steps} steps, {len(msg_ids)} messages")
    return problems


def check_reset_while_waiting():
    """A message sent by someone else than the scenario runner (a future real app) waits on pause:
    reset must be refused, so the old message cannot reach freshly reset apps."""
    import threading
    problems = []
    fresh("pause")
    ex = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                     "examples", "p2p-same-psp", "00-app-payment-initiation.json"), encoding="utf-8"))
    body = dict(ex["body"], MessageIdentification="APPA-RELAYCHECK-0001")
    answer = {}

    def send():
        req = urllib.request.Request(RELAY + "/r/app-a/psp-a/i1/messages", data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", **ex["http"]["headers"]})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                answer["r"] = (r.status, json.loads(r.read()))
        except Exception as e:  # reported below
            answer["r"] = repr(e)

    t = threading.Thread(target=send)
    t.start()
    if not wait_for(lambda: http("GET", "/control/history")[1]["control"]["waiting"], 5):
        problems.append("the app's message did not arrive at the relay")
    status, r = http("POST", "/control/reset")
    if status != 409:
        problems.append(f"reset while a message waits: expected 409, got {status} {r}")
    http("POST", "/control/delay", {"seconds": 0})
    http("POST", "/control/mode", {"mode": "play"})
    t.join(30)
    if not (isinstance(answer.get("r"), tuple) and answer["r"][1].get("ReturnCode") == 0):
        problems.append(f"the waiting payment should still go through after play: {answer.get('r')}")
    return problems


def check_play_delay():
    problems = []
    fresh("play", 0.25)
    t0 = time.time()
    http("POST", "/control/scenarios/p2p-two-psps")
    done = wait_for(finished, 30)
    took = time.time() - t0
    n = len(events(["message"]))
    if not done or not done.get("ok"):
        problems.append(f"scenario did not finish ok: {done}")
    if took < n * 0.25 * 0.9:
        problems.append(f"{n} messages at 0.25 s each took only {took:.2f} s")
    # the ledger booking must appear before the status pushes that follow it
    seq = [(e["type"], e.get("kind"), e.get("path", "")) for e in events(["message", "internal"])]
    ledger = next((i for i, x in enumerate(seq) if x[1] == "ledger"), None)
    push = next((i for i, x in enumerate(seq) if x[0] == "message" and x[2].endswith("/status")), None)
    if ledger is None or push is None or ledger > push:
        problems.append(f"ledger booking not shown before the status push: {seq}")
    print(f"   play: {n} messages in {took:.2f} s")
    return problems


def check_actions():
    problems = []
    cases = [({"action": "pay", "payer": "ben", "payee": "anna", "amount": "12.50", "text": "Coffee"},
              {"ben": -12.5, "anna": 12.5}, {}),
             ({"action": "fund", "payer": "clara", "amount": "30"}, {"clara": 30}, {"clara": -30}),
             ({"action": "defund", "payer": "anna", "amount": "20.00"}, {"anna": -20}, {"anna": 20})]
    for body, d_euro, d_giro in cases:
        fresh("play", 0)
        before = balances()
        status, r = http("POST", "/control/actions", body)
        done = wait_for(finished, 15)
        if status != 202 or not done or not done.get("ok"):
            problems.append(f"{body['action']}: start {status} {r}, end {done}")
            continue
        time.sleep(0.5)
        after = balances()
        for who in before:
            de = after[who][0] - before[who][0]
            dg = after[who][1] - before[who][1]
            if de != Decimal(str(d_euro.get(who, 0))) or dg != Decimal(str(d_giro.get(who, 0))):
                problems.append(f"{body['action']}: {who} changed by {de} digital euro / {dg} giro")
        kinds = {e.get("kind") for e in events(["internal"])}
        if "ledger" not in kinds or (body["action"] != "pay" and "giro" not in kinds):
            problems.append(f"{body['action']}: inside-the-app steps missing from the feed (got {kinds})")
    return problems


def check_refusals():
    problems = []
    fresh("play", 0)
    for body in ({"action": "pay", "payer": "anna", "payee": "anna", "amount": "5"},
                 {"action": "pay", "payer": "anna", "payee": "ben", "amount": "-5"},
                 {"action": "pay", "payer": "zoe", "payee": "ben", "amount": "5"},
                 {"action": "steal", "payer": "anna", "amount": "5"},
                 {"action": "fund", "payer": "anna", "amount": "1.234"}):
        status, r = http("POST", "/control/actions", body)
        if status != 400 or not isinstance(r, dict) or r.get("ok") is not False:
            problems.append(f"{body} should be refused, got {status} {r}")
    for path, body, code in (("/control/mode", {"mode": "fast"}, 400), ("/control/delay", {"seconds": 99}, 400),
                             ("/control/step", None, 409), ("/control/scenarios/nope", None, 404),
                             ("/control/holding-limit", {"amount": "lots"}, 400),
                             ("/control/holding-limit", {"amount": "inf"}, 400),
                             ("/control/holding-limit", {"amount": "99999999999999999999"}, 400)):
        status, _ = http("POST", path, body)
        if status != code:
            problems.append(f"POST {path} {body}: expected {code}, got {status}")
    status, _ = http("POST", "/r/app-a/nowhere/i1/messages", {})
    if status != 404:
        problems.append(f"unknown route: expected 404, got {status}")
    if events(["message"]):
        problems.append("refused commands must not send messages")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--start", action="store_true", help="start the apps and the relay, stop them afterwards")
    args = ap.parse_args()
    procs = []
    if args.start:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import run_local
        run_local.use_relay("play", "0")
        log_dir = tempfile.mkdtemp(prefix="desim-relay-")
        procs = run_local.start_all(log_dir)
    else:
        try:
            http("GET", "/health")
        except (urllib.error.URLError, OSError):
            raise SystemExit("The relay is not running. Start  python3 tools/run_local.py --control-room  or use --start.")
    results = []
    try:
        for name, fn in (("pause and step", check_pause_and_step), ("reset while a message waits", check_reset_while_waiting),
                         ("play with a delay", check_play_delay),
                         ("free actions", check_actions), ("refusals", check_refusals)):
            print(f"── {name}")
            try:
                results.append((name, fn()))
            except Exception as e:  # report and go on with the next check
                results.append((name, [f"crashed: {e!r}"]))
        fresh("play", 0)
    finally:
        if procs:
            run_local.stop_all(procs)
    failed = 0
    print("\n══ Summary")
    for name, problems in results:
        print(f"   {'PASS' if not problems else 'FAIL'}  {name}")
        for p in problems:
            print(f"         - {p}")
        failed += bool(problems)
    print(f"   {len(results) - failed} of {len(results)} passed.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

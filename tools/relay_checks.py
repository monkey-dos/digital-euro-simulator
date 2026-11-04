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
  7. wrong input is refused with a clear error, and an unknown route gives 404;
  8. Helicopter Money (ADR 0009): digital euro and giro money for people at both banks, the
     holding limit, refusals, the bookkeeping check, the messages in the feed and at the gate, reset;
  9. Helicopter Money guards: parallel drops (one 202, one 409), the relay route refusing /sim/ paths and the
     game master as sender (403), bodies that are not a JSON object (400).
  10. Helicopter Money with an app stopped during a drop (needs --start): PSP A down after the DESP booked
     (undone, message says so), DESP down at the first call (nothing booked), slot free again afterwards;
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
PROCS: list = []     # the apps started by --start (empty when they were started by someone else)
LOG_DIR = None


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


DESP_BIC_A = "SIMADEF0XXX"


def apps_state():
    _, s = http("GET", "/control/state")
    return s.get("apps", {})


def customer(state, slug, first):
    return next(c for c in state[slug]["customers"] if c["name"].split()[0].lower() == first)


def helicopter(person, account, amount, wait=True):
    """Send the command; wait until the drop has finished (feed event)."""
    n_before = len(events(["scenario"]))
    status, r = http("POST", "/control/helicopter-money", {"person": person, "account": account, "amount": amount})
    if status != 202 or not wait:
        return status, r, None
    done = wait_for(lambda: next((e for e in events(["scenario"])[n_before:] if e["status"] in ("finished", "failed")), None), 15)
    time.sleep(0.4)
    return status, r, done


def money_ok(problems, label):
    d = apps_state()["desp"]
    if not d["moneyCheck"]["ok"]:
        problems.append(f"{label}: DESP money check failed: {d['moneyCheck']}")
    return d


def check_helicopter_money():
    problems = []
    fresh("play", 0)
    before = apps_state()
    anna0, ben0, clara0 = (customer(before, s, n) for s, n in (("psp-a", "anna"), ("psp-b", "ben"), ("psp-a", "clara")))
    dca0 = {b: Decimal(v) for b, v in before["desp"]["dcaBalances"].items()}

    # digital euro: a person at PSP A and a person at PSP B
    for slug, who, c0 in (("psp-a", "anna", anna0), ("psp-b", "ben", ben0)):
        status, r, done = helicopter(who, "digital-euro", "100.00")
        if status != 202 or not r.get("ok") or not done or not done.get("ok"):
            problems.append(f"digital euro for {who}: {status} {r} {done}")
            continue
        st = apps_state()
        c = customer(st, slug, who)
        if Decimal(c["digitalEuro"]) != Decimal(c0["digitalEuro"]) + 100 or c["giro"] != c0["giro"]:
            problems.append(f"{who}: digital euro {c0['digitalEuro']} -> {c['digitalEuro']}, giro {c0['giro']} -> {c['giro']}")
        d = money_ok(problems, f"digital euro for {who}")
        if {b: Decimal(v) for b, v in d["dcaBalances"].items()} != dca0:
            problems.append(f"{who}: a DCA changed for digital euro Helicopter Money: {d['dcaBalances']}")
        if st[slug]["helicopterMoney"]["digitalEuro"] != "100.00":
            problems.append(f"{who}: bank Helicopter Money ledger: {st[slug]['helicopterMoney']}")
        entry = next(e for e in d["entries"] if e["entryId"] == next(
            u["entry"] for u in json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "test-data.json")))["users"].values() if u["name"].lower().startswith(who)))
        if Decimal(entry["balance"]) != Decimal(c["digitalEuro"]):
            problems.append(f"{who}: DESP entry {entry['balance']} differs from the bank's copy {c['digitalEuro']}")
    d = apps_state()["desp"]
    if d["helicopterMoney"]["digitalEuro"] != "200.00" or d["helicopterMoney"]["dca"]:
        problems.append(f"DESP totals after two digital euro drops: {d['helicopterMoney']}")

    # giro money via the bank
    status, r, done = helicopter("clara", "giro", "250.00")
    if status != 202 or not done or not done.get("ok"):
        problems.append(f"giro for clara: {status} {r} {done}")
    st = apps_state()
    c = customer(st, "psp-a", "clara")
    d = money_ok(problems, "giro for clara")
    if Decimal(c["giro"]) != Decimal(clara0["giro"]) + 250 or c["digitalEuro"] != clara0["digitalEuro"]:
        problems.append(f"clara: giro {clara0['giro']} -> {c['giro']}, digital euro {clara0['digitalEuro']} -> {c['digitalEuro']}")
    if Decimal(d["dcaBalances"][DESP_BIC_A]) != dca0[DESP_BIC_A] + 250 or d["helicopterMoney"]["dca"] != {DESP_BIC_A: "250.00"}:
        problems.append(f"DCA of PSP A after giro Helicopter Money: {d['dcaBalances']} / {d['helicopterMoney']}")
    hm = st["psp-a"]["helicopterMoney"]
    if hm["giro"] != "250.00" or hm["dcaReceived"] != "250.00" or not hm["ok"] or d["helicopterMoney"]["dca"].get(DESP_BIC_A) != hm["giro"]:
        problems.append(f"bank ledger / cross-check: {hm}")
    if st["psp-b"]["helicopterMoney"]["giro"] != "0.00":
        problems.append("PSP B must not see giro Helicopter Money meant for PSP A")
    ledger = [e for e in events(["internal"]) if e.get("kind") == "bank-ledger"]
    legs = [b["account"] for b in (ledger[-1]["body"]["bookings"] if ledger else [])]
    if legs != ["DCA at the central bank", "giro of Clara Weber"]:
        problems.append(f"bank ledger event missing or wrong: {ledger}")
    if not any(e.get("kind") == "ledger" and (e.get("body") or {}).get("helicopterMoney") for e in events(["internal"])):
        problems.append("no DESP ledger event marked as Helicopter Money")
    # messages in the feed come from the game master and carry the plain sim endpoints
    gm = [m for m in events(["message"]) if m["fromId"] == "game-master"]
    if len(gm) != 2 * 2 + 2 or {m["path"] for m in gm} != {"/sim/helicopter-money"} or any(m["interface"] != "sim (not ECB)" for m in gm):
        problems.append(f"game master messages: {[(m['from'], m['toId'], m['path']) for m in gm]}")
    if {m["toId"] for m in gm if m["kind"] == "request"} != {"desp", "psp-a", "psp-b"}:
        problems.append("game master requests should reach the DESP and both banks")

    # reset brings every total back to 0
    fresh("play", 0)
    st = apps_state()
    zero = (st["desp"]["helicopterMoney"] == {"digitalEuro": "0.00", "dca": {}}
            and all(st[s]["helicopterMoney"]["giro"] == "0.00" and st[s]["helicopterMoney"]["digitalEuro"] == "0.00"
                    and not st[s]["helicopterMoney"]["bookings"] for s in ("psp-a", "psp-b")))
    if not zero:
        problems.append(f"totals after reset: {st['desp']['helicopterMoney']}")
    money_ok(problems, "after reset")

    # holding limit (bank's view: balance + incoming + amount)
    http("POST", "/control/holding-limit", {"amount": "130.00"})
    status, r = http("POST", "/control/helicopter-money", {"person": "anna", "account": "digital-euro", "amount": "10.01"})
    if status != 409 or r.get("ok") is not False or "holding limit" not in r.get("error", ""):
        problems.append(f"over the holding limit: expected a clear 409, got {status} {r}")
    status, r, done = helicopter("anna", "digital-euro", "10.00")  # exactly at the limit is fine
    if status != 202 or not done or not done.get("ok"):
        problems.append(f"exactly up to the limit: {status} {r} {done}")
    status, r, done = helicopter("anna", "giro", "5000.00")  # giro money does not count against the limit
    if status != 202 or not done or not done.get("ok"):
        problems.append(f"giro money must ignore the holding limit: {status} {r} {done}")
    money_ok(problems, "holding limit")

    # refused while a scenario runs, and while a message waits at the gate
    fresh("pause")
    http("POST", "/control/scenarios/p2p-same-psp")
    wait_for(lambda: events(["message"]), 5)
    status, r = http("POST", "/control/helicopter-money", {"person": "anna", "account": "giro", "amount": "5"})
    if status != 409:
        problems.append(f"Helicopter Money while a scenario runs: expected 409, got {status} {r}")
    http("POST", "/control/delay", {"seconds": 0})
    http("POST", "/control/mode", {"mode": "play"})
    wait_for(finished, 15)
    time.sleep(0.5)
    money_ok(problems, "after the scenario")

    # bad input: nothing is sent, nothing is booked
    fresh("play", 0)
    for body, code in (({"person": "anna", "account": "giro", "amount": "0"}, 400),
                       ({"person": "anna", "account": "giro", "amount": "-5"}, 400),
                       ({"person": "anna", "account": "giro", "amount": "1.234"}, 400),
                       ({"person": "anna", "account": "giro", "amount": "1000000.01"}, 400),
                       ({"person": "anna", "account": "giro", "amount": "lots"}, 400),
                       ({"person": "anna", "account": "giro", "amount": "inf"}, 400),
                       ({"person": "anna", "account": "giro"}, 400),
                       ({"person": "zoe", "account": "giro", "amount": "5"}, 404),
                       ({"account": "giro", "amount": "5"}, 404),
                       ({"person": "anna", "account": "savings", "amount": "5"}, 400)):
        status, r = http("POST", "/control/helicopter-money", body)
        if status != code or not isinstance(r, dict) or r.get("ok") is not False or not r.get("error"):
            problems.append(f"{body}: expected {code} with an error text, got {status} {r}")
    if events(["message"]):
        problems.append("refused Helicopter Money must not send messages")
    money_ok(problems, "after refusals")
    status, r, done = helicopter("anna", "giro", "1000000.00")  # the maximum is allowed
    if status != 202 or not done or not done.get("ok"):
        problems.append(f"maximum amount: {status} {r} {done}")
    money_ok(problems, "maximum amount")

    # pause mode: the drop waits at the gate and goes on one step at a time
    fresh("pause")
    status, r = http("POST", "/control/helicopter-money", {"person": "ben", "account": "giro", "amount": "40.00"})
    if status != 202:
        problems.append(f"pause: start {status} {r}")
    wait_for(lambda: events(["message"]), 5)
    time.sleep(0.5)
    if apps_state()["desp"]["helicopterMoney"]["dca"]:
        problems.append("pause: the DESP booked before the first step")
    status, r = http("POST", "/control/helicopter-money", {"person": "ben", "account": "giro", "amount": "1"})
    if status != 409:
        problems.append(f"second drop while one waits: expected 409, got {status}")
    steps = 0
    while not finished() and steps < 12:
        if not wait_for(lambda: http("GET", "/control/history")[1]["control"]["waiting"] or finished(), 5):
            break
        if finished():
            break
        n_rel = len(events(["released"]))
        http("POST", "/control/step")
        steps += 1
        wait_for(lambda: len(events(["released"])) == n_rel + 1, 5)
        time.sleep(0.2)
    done = wait_for(finished, 5)
    gm = [m for m in events(["message"]) if m["fromId"] == "game-master" or m["toId"] == "game-master"]
    if steps != 4 or len(gm) != 4 or not done or not done.get("ok"):
        problems.append(f"pause: {steps} steps, {len(gm)} game master messages, result {done}")
    if apps_state()["desp"]["helicopterMoney"]["dca"].get("SIMBDEF0XXX") != "40.00":
        problems.append("pause: the DESP did not book after the steps")
    d = money_ok(problems, "pause")
    hm_b = apps_state()["psp-b"]["helicopterMoney"]
    if d["helicopterMoney"]["dca"].get("SIMBDEF0XXX") != hm_b["giro"]:
        problems.append(f"pause: cross-check differs: {d['helicopterMoney']} / {hm_b}")

    # the bank refuses after the DESP booked: the DESP booking is undone
    fresh("pause")
    status, r = http("POST", "/control/helicopter-money", {"person": "anna", "account": "digital-euro", "amount": "50.00"})
    for _ in range(2):  # DESP request and answer
        wait_for(lambda: http("GET", "/control/history")[1]["control"]["waiting"], 5)
        http("POST", "/control/step")
        time.sleep(0.4)
    limit_body = {"command": "SET_HOLDING_LIMIT", "amount": {"currency": "EUR", "amount": "100.00"}}
    urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8001/sim/holding-limit", data=json.dumps(limit_body).encode(),
                                                  method="POST", headers={"Content-Type": "application/json"}), timeout=5).read()
    for _ in range(8):  # bank request and answer, then the undo at the DESP
        if finished():
            break
        wait_for(lambda: http("GET", "/control/history")[1]["control"]["waiting"] or finished(), 5)
        http("POST", "/control/step")
        time.sleep(0.4)
    done = wait_for(finished, 5)
    if not done or done["status"] != "failed" or "undone" not in done.get("error", ""):
        problems.append(f"bank refusal should fail the drop and undo it: {done}")
    d = money_ok(problems, "after the undo")
    if d["helicopterMoney"]["digitalEuro"] != "0.00" or Decimal(customer(apps_state(), "psp-a", "anna")["digitalEuro"]) != Decimal(anna0["digitalEuro"]):
        problems.append(f"the undo left money behind: {d['helicopterMoney']}")
    print(f"   helicopter money: pause run took {steps} steps")
    return problems


def check_helicopter_guards():
    """Parallel drops, the relay route keeping /sim/ and the game master sender private, bad bodies."""
    import threading
    problems = []
    fresh("play", 0.2)
    results = {}

    def send(key, path, body):
        results[key] = http("POST", path, body)

    # two drops at the same moment: exactly one may start
    ts = [threading.Thread(target=send, args=(k, "/control/helicopter-money", {"person": "anna", "account": "digital-euro", "amount": "10.00"}))
          for k in ("a", "b")]
    [t.start() for t in ts]
    [t.join() for t in ts]
    codes = sorted(results[k][0] for k in ("a", "b"))
    if codes != [202, 409]:
        problems.append(f"two parallel drops: expected one 202 and one 409, got {codes}")
    wait_for(finished, 15)
    time.sleep(0.5)
    if apps_state()["desp"]["helicopterMoney"]["digitalEuro"] != "10.00":
        problems.append(f"only one of two parallel drops may be booked: {apps_state()['desp']['helicopterMoney']}")
    money_ok(problems, "parallel drops")

    # a drop and a reset at the same moment: not both may succeed
    fresh("play", 0.2)
    results.clear()
    ts = [threading.Thread(target=send, args=("drop", "/control/helicopter-money", {"person": "ben", "account": "giro", "amount": "10.00"})),
          threading.Thread(target=send, args=("reset", "/control/reset", None))]
    [t.start() for t in ts]
    [t.join() for t in ts]
    if results["drop"][0] == 202 and results["reset"][0] == 200:
        problems.append("a drop and a reset were both accepted at the same moment")
    wait_for(finished, 15) if results["drop"][0] == 202 else None
    time.sleep(0.5)
    money_ok(problems, "drop and reset at once")

    # the apps' /sim/ endpoints and the game master are not reachable through the relay route
    fresh("play", 0)
    before = apps_state()
    for path, body in (("/r/game-master/desp/sim/helicopter-money", {"target": "dca", "bic": DESP_BIC_A, "amount": "5.00", "helicopterId": "HM-EVIL"}),
                       ("/r/game-master/desp/v1/payment-instructions", {}),
                       ("/r/app-a/psp-a/sim/helicopter-money", {"account": "giro", "dean": "EU4900000000000001", "amount": "5.00", "helicopterId": "HM-EVIL"}),
                       ("/r/psp-a/desp/sim/reset", None),
                       ("/r/app-a/psp-a/%73im/reset", None),
                       ("/r/app-a/psp-a//sim/reset", None),
                       ("/r/app-a/psp-a/./sim/reset", None),
                       ("/r/psp-a/desp/./sim/helicopter-money", {"target": "dca", "bic": DESP_BIC_A, "amount": "5.00", "helicopterId": "HM-EVIL2"}),
                       ("/r/psp-a/desp/v1/../sim/reset", None),
                       ("/r/psp-a/desp/v1/%2e%2e/sim/helicopter-money", {"target": "dca", "bic": DESP_BIC_A, "amount": "5.00", "helicopterId": "HM-EVIL3"}),
                       ("/r/psp-a/desp/%2e/sim/reset", None),
                       ("/r/psp-a/desp/%252e/sim/reset", None),
                       ("/r/psp-a/desp/%2E%2E/sim/reset", None),
                       ("/r/psp-a/desp/v1%2f..%2fsim/reset", None),
                       ("/r/psp-a/desp/health", None)):
        status, r = http("POST", path, body)
        if status != 403:
            problems.append(f"{path}: expected 403, got {status} {r}")
    # the books and every app's state are exactly as before (a reset or a minted DCA would show here)
    after = apps_state()
    strip = lambda st: {k: {kk: vv for kk, vv in (v or {}).items() if kk not in ("transactions",)} for k, v in st.items()}
    if strip(after) != strip(before):
        problems.append("a refused /sim/ call changed the state of an app")
    if after["desp"]["dcaBalances"] != before["desp"]["dcaBalances"] or customer(after, "psp-a", "anna")["giro"] != customer(before, "psp-a", "anna")["giro"]:
        problems.append("a refused /sim/ call changed the books")
    if events(["message"]):
        problems.append("a refused /sim/ call must not appear as a message")

    # a body that is not a JSON object is a 400
    for raw in (b"[1,2]", b"\"anna\"", b"nonsense", b"null", b""):
        req = urllib.request.Request(RELAY + "/control/helicopter-money", data=raw, method="POST", headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=10)
            code = 200
        except urllib.error.HTTPError as e:
            code = e.code
        if code != 400:
            problems.append(f"body {raw!r}: expected 400, got {code}")
    money_ok(problems, "guards")
    return problems


def check_helicopter_app_down():
    """An app stops during a drop: the books stay balanced, the slot is free again, the message names the right side."""
    if not PROCS:
        print("   (skipped: needs --start, to stop and restart the apps)")
        return []
    import run_local
    problems = []

    def drop_with_app_down(app, person, account):
        fresh("play", 0)
        run_local.stop_all([next(p for p in PROCS if p.sim_name == app)])
        n = len(events(["scenario"]))
        try:
            status, r = http("POST", "/control/helicopter-money", {"person": person, "account": account, "amount": "25.00"})
            done = wait_for(lambda: next((e for e in events(["scenario"])[n:] if e["status"] in ("finished", "failed")), None), 20) if status == 202 else None
        finally:
            run_local.restart(PROCS, app, LOG_DIR)
        return status, done

    # PSP A is down when the bank is told: the DESP booked (new DCA money), so it must be undone
    status, done = drop_with_app_down("PSP A", "anna", "giro")
    err = (done or {}).get("error", "")
    if status != 202 or not done or done["status"] != "failed":
        problems.append(f"PSP A down: the drop should fail: {status} {done}")
    if "PSP A could not be reached" not in err or "central platform booking was undone" not in err or "FAILED" in err:
        problems.append(f"PSP A down: the message should say PSP A was unreachable and the central platform booking was undone: {err!r}")
    d = apps_state()["desp"]
    if d["helicopterMoney"]["dca"] or not d["moneyCheck"]["ok"] or d["dcaBalances"][DESP_BIC_A] != "1000000.00":
        problems.append(f"PSP A down: the DESP booking was not undone: {d['helicopterMoney']} {d['dcaBalances']}")
    fresh("play", 0)
    status, r, done = helicopter("anna", "giro", "5.00")
    if status != 202 or not done or not done.get("ok"):
        problems.append(f"PSP A down: the slot is not free again afterwards: {status} {r} {done}")
    money_ok(problems, "PSP A down")

    # the DESP is down at the first call: nothing arrived, nothing was booked, nothing to undo
    status, done = drop_with_app_down("DESP", "ben", "giro")
    err = (done or {}).get("error", "")
    if status != 202 or not done or done["status"] != "failed":
        problems.append(f"DESP down: the drop should fail: {status} {done}")
    if "central platform could not be reached" not in err or "Nothing was booked" not in err or "FAILED" in err or "undo" in err.lower():
        problems.append(f"DESP down: the message should say nothing was booked and nothing needed undoing: {err!r}")
    fresh("play", 0)  # the DESP came back with the seed data
    d = apps_state()["desp"]
    if d["helicopterMoney"]["dca"] or d["helicopterMoney"]["digitalEuro"] != "0.00" or not d["moneyCheck"]["ok"]:
        problems.append(f"DESP down: books not clean after restart: {d['helicopterMoney']}")
    status, r, done = helicopter("ben", "digital-euro", "5.00")
    if status != 202 or not done or not done.get("ok"):
        problems.append(f"DESP down: the slot is not free again afterwards: {status} {r} {done}")
    money_ok(problems, "DESP down")
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
        PROCS.extend(procs)
        globals()["LOG_DIR"] = log_dir
    else:
        try:
            http("GET", "/health")
        except (urllib.error.URLError, OSError):
            raise SystemExit("The relay is not running. Start  python3 tools/run_local.py --control-room  or use --start.")
    results = []
    try:
        for name, fn in (("pause and step", check_pause_and_step), ("reset while a message waits", check_reset_while_waiting),
                         ("play with a delay", check_play_delay),
                         ("free actions", check_actions), ("refusals", check_refusals),
                         ("Helicopter Money", check_helicopter_money), ("Helicopter Money guards", check_helicopter_guards),
                         ("Helicopter Money, app down", check_helicopter_app_down)):
            print(f"── {name}")
            try:
                results.append((name, fn()))
            except Exception as e:  # report and go on with the next check
                results.append((name, [f"crashed: {e!r}"]))
        fresh("play", 0)
    finally:
        if procs:
            run_local.stop_all(PROCS)  # PROCS also holds apps restarted by a check
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

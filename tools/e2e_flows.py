#!/usr/bin/env python3
"""Play the six example flows live through the running apps and check them.

    python3 tools/run_local.py          # in one terminal
    python3 tools/e2e_flows.py          # in another
or
    python3 tools/e2e_flows.py --start  # starts and stops the apps itself

For every scenario in /examples (same order and amounts) the script resets all
apps to the test data, sends the example's I1 message to the bank exactly as in
the example file, and then checks:
  1. the app gets ReturnCode 0;
  2. every message the apps exchanged has the same shape as the example:
     path, status, headers, body (IDs and timestamps excepted; encrypted parts
     compared after decoding), in the same order per app, including the giro
     steps (block / debit / credit) and the ledger bookings;
  3. end balances on the DESP ledger, the DCAs and the giro accounts match the
     example, nothing is left blocked or pending, and the money check holds
     (digital euro in circulation = opening balances + net DCA debits).
Then it plays rejections, which must change nothing, and regression checks:
parallel payments against the holding limit, a payment to oneself at the DESP
and (with --start only) a funding while the DESP is down.
Exit code 0 only if everything matches. Uses only the Python standard library.
"""
import argparse
import base64
import shutil
import threading
import glob
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.join(ROOT, "examples")
URL = {"DESP": "http://127.0.0.1:8000", "PSP A": "http://127.0.0.1:8001", "PSP B": "http://127.0.0.1:8002"}
# Where the banking app's messages (I1) go. With --via-relay they pass the network relay like in the control room.
I1_URL = dict(URL)
RELAY_I1 = {"PSP A": "http://127.0.0.1:8100/r/app-a/psp-a", "PSP B": "http://127.0.0.1:8100/r/app-b/psp-b"}
TD = json.load(open(os.path.join(EX, "test-data.json"), encoding="utf-8"))
FLOWS = ["p2p-same-psp", "p2p-two-psps", "p2p-reverse-waterfall-same-psp",
         "funding-same-psp", "defunding-same-psp", "p2p-waterfall-two-psps"]
# Values that differ on every run: compared for presence, not value.
VOLATILE = {"UETR", "paymentInstructionId", "fundingId", "defundingId", "acceptanceDateTime", "settlementDateTime",
            "settlementBusinessDay", "CreationDateTime", "MessageIdentification", "TransactionDate"}
HEADER_VALUES = {"Content-Type", "Requesting-Agent", "Sim-User-DEAN"}  # compared by value; others by name
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
D = Decimal


# ---------------------------------------------------------------- HTTP (stdlib only)

def http(method, url, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, json.loads(raw) if raw else None


def get(app, path):
    return http("GET", URL[app] + path)[1]


def apps_up():
    for app, url in URL.items():
        try:
            get(app, "/health")
        except (urllib.error.URLError, OSError):
            return app
    return None


# ---------------------------------------------------------------- normalising messages for comparison

def norm_body(o, key=None):
    if isinstance(o, dict):
        return {k: norm_body(v, k) for k, v in o.items()}
    if isinstance(o, list):
        return [norm_body(v) for v in o]
    if key in VOLATILE:
        return "<varies>"
    if isinstance(o, str) and o.startswith("SIMENC:"):
        return {"decrypted": norm_body(json.loads(base64.b64decode(o[7:])))}
    if isinstance(o, float):
        return D(str(o))
    return o


def norm_headers(h):
    return {k: (v if k in HEADER_VALUES else "<present>") for k, v in sorted((h or {}).items())}


def from_step(step):
    """Normalised form of one example step, or None if the apps don't produce it as a message."""
    if step["to"] == "DESP ledger":
        return {"kind": "ledger", "actor": "DESP", "bookings": norm_bookings(step["body"]["bookings"])}
    if step["to"].endswith("core banking"):
        return {"kind": "giro", "actor": step["from"], "body": step["body"]}
    http_ = step.get("http")
    if not http_:
        return None  # e.g. the game master command, sent separately
    actor = step["to"] if step["interface"] == "I1" and http_.get("method") else step["from"]
    return {"kind": "http", "actor": actor, "from": step["from"], "to": step["to"],
            "what": f"{http_['method']} {UUID.sub('{id}', http_['path'])}" if http_.get("method") else http_["status"],
            "headers": norm_headers(http_.get("headers")), "body": norm_body(step["body"])}


def from_event(e):
    if e["kind"] == "ledger":
        return {"kind": "ledger", "actor": "DESP", "bookings": norm_bookings(e["body"]["bookings"])}
    if e["kind"] == "giro":
        return {"kind": "giro", "actor": e["app"], "body": e["body"]}
    if e["kind"] != "http" or (e["path"] or "").startswith("/sim/") or " /sim/" in (e.get("in_reply_to") or ""):
        return None  # simulation commands (game master) are not part of the ECB message flow
    if e["direction"] == "received" and not (e["method"] and e["path"].startswith("/i1/")):
        return None  # each message is taken from its sender; I1 requests from the bank that received them
    return {"kind": "http", "actor": e["app"], "from": e["from"], "to": e["to"],
            "what": f"{e['method']} {UUID.sub('{id}', e['path'])}" if e["method"] else e["status"],
            "headers": norm_headers(e["headers"]), "body": norm_body(e["body"])}


def norm_bookings(bookings):
    return sorted(({"entry": b["entry"], "before": b["before"], "change": b["change"], "after": b["after"]}
                   for b in bookings), key=lambda b: b["entry"])


def label(m):
    if m["kind"] == "http":
        return f"{m['from']} → {m['to']}: {m['what']}"
    return f"{m['actor']}: {m['kind']} {json.dumps(m.get('body') or m.get('bookings'), default=str)[:90]}"


def diff(a, b, path=""):
    """First difference between two normalised values, as text."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                return f"{path}.{k}: sent by the app, not in the example"
            if k not in b:
                return f"{path}.{k}: in the example, not sent by the app"
            d = diff(a[k], b[k], f"{path}.{k}")
            if d:
                return d
        return None
    return None if a == b else f"{path or 'value'}: example {a!r}, app {b!r}"


def compare_messages(steps, events):
    """Per app, the messages must appear in the same order as in the example."""
    problems = []
    expected = [m for m in (from_step(s) for s in steps) if m]
    actual = [m for m in (from_event(e) for e in events) if m]
    for actor in sorted({m["actor"] for m in expected + actual}):
        exp = [m for m in expected if m["actor"] == actor]
        act = [m for m in actual if m["actor"] == actor]
        for i in range(max(len(exp), len(act))):
            if i >= len(exp):
                problems.append(f"{actor}: extra message #{i + 1}: {label(act[i])}")
            elif i >= len(act):
                problems.append(f"{actor}: missing message #{i + 1}: {label(exp[i])}")
            else:
                d = diff(exp[i], act[i])
                if d:
                    problems.append(f"{actor} message #{i + 1} ({label(exp[i])}): {d}")
    return problems


# ---------------------------------------------------------------- state

def snapshot():
    desp, a, b = get("DESP", "/sim/state"), get("PSP A", "/sim/state"), get("PSP B", "/sim/state")
    s = {"entries": {e["entryId"]: D(e["balance"]) for e in desp["entries"]},
         "dca": {bic: D(v) for bic, v in desp["dcaBalances"].items()},
         "money_ok": desp["moneyCheck"]["ok"], "money": desp["moneyCheck"],
         "customers": {}, "pending": a["pendingTransactions"] + b["pendingTransactions"]}
    for psp in (a, b):
        for c in psp["customers"]:
            s["customers"][c["DEAN"]] = {k: D(c[k]) for k in ("digitalEuro", "giro", "giroBlocked")}
    return s


def seed_expectation():
    users = TD["users"]
    return ({u["entry"]: D(u["balance"]) for u in users.values()},
            {TD["banks"][k]["bic"]: D(v) for k, v in TD["dcaBalances"].items()},
            {u["dean"]: D(u["giro"]) for u in users.values()})


def expected_end(steps):
    """End balances according to the example: ledger 'after' values and giro steps applied to the test data."""
    entries, dca, giro = seed_expectation()
    names = {f"DCA of PSP {k}": v["bic"] for k, v in TD["banks"].items()}
    by_name = {u["name"]: u["dean"] for u in TD["users"].values()}
    for s in steps:
        if s["to"] == "DESP ledger":
            for b in s["body"]["bookings"]:
                if b["entry"] in names:
                    dca[names[b["entry"]]] = D(b["after"])
                else:
                    entries[b["entry"]] = D(b["after"])
        elif s["to"].endswith("core banking"):
            dean, a = by_name[s["body"]["account"].replace("giro of ", "")], D(s["body"]["amount"]["amount"])
            if s["body"]["action"] in ("debit blocked amount", "debit"):
                giro[dean] -= a
            elif s["body"]["action"] == "credit":
                giro[dean] += a
    return entries, dca, giro


def compare_state(st, entries, dca, giro):
    problems = []
    for e, v in entries.items():
        if st["entries"].get(e) != v:
            problems.append(f"ledger entry {e}: expected {v}, DESP has {st['entries'].get(e)}")
    for bic, v in dca.items():
        if st["dca"].get(bic) != v:
            problems.append(f"DCA {bic}: expected {v}, DESP has {st['dca'].get(bic)}")
    for u in TD["users"].values():
        c = st["customers"][u["dean"]]
        if c["giro"] != giro[u["dean"]]:
            problems.append(f"giro of {u['name']}: expected {giro[u['dean']]}, bank has {c['giro']}")
        if c["giroBlocked"] != 0:
            problems.append(f"giro of {u['name']}: {c['giroBlocked']} still blocked")
        if c["digitalEuro"] != entries[u["entry"]]:
            problems.append(f"{u['name']}: bank's copy {c['digitalEuro']} differs from ledger {entries[u['entry']]}")
    if not st["money_ok"]:
        problems.append(f"money check failed: {st['money']}")
    if st["pending"]:
        problems.append(f"{st['pending']} transaction(s) still pending at the banks")
    return problems


def print_balances(st):
    for u in TD["users"].values():
        c = st["customers"][u["dean"]]
        print(f"     {u['name']:<14} PSP {u['bank']}   digital euro {c['digitalEuro']:>8}   giro {c['giro']:>8}")
    for k, b in TD["banks"].items():
        print(f"     DCA of PSP {k}            {st['dca'][b['bic']]:>12}")
    m = st["money"]
    print(f"     Money check: {m['digitalEuroInCirculation']} in circulation = {m['openingBalances']} opening "
          f"+ {m['netDcaDebitsSinceStart']} net DCA debits → {'OK' if m['ok'] else 'BROKEN'}")


def describe(events):
    """Plain-English summary of what happened, from the apps' own log events."""
    names = {u["entry"]: u["name"].split()[0] for u in TD["users"].values()}
    lines = []
    for e in events:
        if e["kind"] == "ledger":
            parts = [f"{names.get(b['entry'], b['entry'])} {b['change']} → {b['after']}" for b in e["body"]["bookings"]]
            lines.append("The DESP settled in one atomic step: " + "; ".join(parts) + ".")
        elif e["kind"] == "giro":
            lines.append(f"{e['app']} core banking: {e['body']['action']} {e['body']['amount']['amount']} EUR on the {e['body']['account']}.")
        elif e["kind"] == "http" and e["direction"] == "sent" and e["method"] == "POST" and e["path"] == "/v1/payment-instructions" and e["app"] == "DESP":
            lines.append(f"The DESP forwarded the instruction to {e['to']} (without the payer's ledger entry).")
        elif e["kind"] == "http" and e["direction"] == "sent" and e["status"] == 201 and e["app"].startswith("PSP") and isinstance(e["body"], dict):
            if e["body"].get("paymentDefundingObject"):
                lines.append(f"{e['app']} accepted and asked to sweep {e['body']['paymentDefundingObject']['amount']['amount']} EUR to the giro account (waterfall).")
            else:
                lines.append(f"{e['app']} accepted and added its customer's ledger entry.")
    return lines


# ---------------------------------------------------------------- running flows

def reset_all():
    for app in URL:
        status, _ = http("POST", URL[app] + "/sim/reset")
        if status != 200:
            raise SystemExit(f"Could not reset {app} (HTTP {status})")


def marks():
    return {app: (get(app, "/sim/events?since=0")["events"] or [{"seq": 0}])[-1]["seq"] for app in URL}


def events_since(m):
    out = []
    for app in URL:
        out += get(app, f"/sim/events?since={m[app]}")["events"]
    return sorted(out, key=lambda e: (e["time"], e["app"], e["seq"]))


def settle_down():
    """Background work (status pushes to the other bank, giro credits) may finish just after the app's answer."""
    deadline = time.time() + 5
    while time.time() < deadline:
        time.sleep(0.2)
        if get("PSP A", "/sim/state")["pendingTransactions"] + get("PSP B", "/sim/state")["pendingTransactions"] == 0:
            time.sleep(0.2)
            return


def send_i1(step):
    return http("POST", I1_URL[step["to"]] + step["http"]["path"], step["body"], step["http"]["headers"])


def run_flow(folder):
    steps = [json.load(open(f, encoding="utf-8")) for f in sorted(glob.glob(os.path.join(EX, folder, "[0-9][0-9]-*.json")))]
    title = open(os.path.join(EX, folder, "README.md"), encoding="utf-8").readline().lstrip("# ").strip()
    print(f"\n── {folder}: {title}")
    reset_all()
    gm = next((s for s in steps if s["from"] == "Game Master"), None)
    m = marks()
    try:
        if gm:  # the example's game master command, sent to PSP B (the payee's bank)
            status, _ = http("POST", URL["PSP B"] + "/sim/holding-limit", gm["body"])
            print(f"   Game master set PSP B's holding limit to {gm['body']['amount']['amount']} EUR (HTTP {status}).")
        i1 = next(s for s in steps if s["interface"] == "I1" and s.get("http", {}).get("method"))
        status, answer = send_i1(i1)
        settle_down()
    finally:
        if gm:
            http("POST", URL["PSP B"] + "/sim/holding-limit", {"command": "SET_HOLDING_LIMIT", "amount": {"currency": "EUR", "amount": TD["holdingLimit"]}})
    events = events_since(m)
    problems = []
    if status != 200 or not answer or answer.get("ReturnCode") != 0:
        problems.append(f"app answer: HTTP {status}, {answer}")
    problems += compare_messages(steps, events)
    st = snapshot()
    problems += compare_state(st, *expected_end(steps))
    for line in describe(events):
        print("   " + line)
    print(f"   The app got ReturnCode {answer.get('ReturnCode') if answer else '?'}. Balances now:")
    print_balances(st)
    return problems


def dean_with_check(serial: int) -> str:
    bban = "0" + f"{serial:013d}"
    num = int("".join(str(ord(c) - 55) if c.isalpha() else c for c in bban + "EU00"))
    return f"EU{98 - num % 97:02d}{bban}"


REJECTIONS = [
    # (title, bank, logged-in user, body changes, expected StatusReason, what it shows)
    ("Clara tries to pay Anna 1000.00 EUR (40.00 digital euro + 900.00 giro is not enough)", "PSP A", "clara",
     {"Amount": 1000.0, "Name": "Anna Schmidt", "ProxyAccount": "+4915100000001"}, "XBAL",
     "PSP A checks digital euro plus giro before sending anything to the DESP."),
    ("Anna tries to pay an unknown phone number", "PSP A", "anna",
     {"Amount": 10.0, "Name": "Nobody", "ProxyAccount": "+4915100000099"}, "XALI",
     "The DESP's alias lookup answers 404; PSP A stops."),
    ("Anna pays a DEAN that PSP B does not know (payee bank rejects, Fig. 8)", "PSP A", "anna",
     {"Amount": 10.0, "Name": "Nobody", "PaymentMethod": "DEAN", "PayeeDEAN": dean_with_check(99),
      "CreditorAgent": TD["banks"]["B"]["bic"], "ProxyAccount": None, "ProxyAccountType": None}, "XACC",
     "PSP B rejects the forwarded instruction; the DESP settles nothing and tells only PSP A."),
]


def run_rejection(title, bank, user, changes, code, why):
    print(f"\n── rejection: {title}")
    reset_all()
    before = snapshot()
    template = json.load(open(os.path.join(EX, "p2p-two-psps", "00-app-payment-initiation.json"), encoding="utf-8"))
    body = dict(template["body"], MessageIdentification=f"E2E-REJ-{code}")
    for k, v in changes.items():
        if v is None:
            body.pop(k, None)
        else:
            body[k] = v
    m = marks()
    status, answer = http("POST", I1_URL[bank] + "/i1/messages", body, {"Sim-User-DEAN": TD["users"][user]["dean"]})
    settle_down()
    events = events_since(m)
    after = snapshot()
    problems = []
    if status != 200 or not answer or answer.get("ReturnCode") != 1 or answer.get("StatusReason") != code:
        problems.append(f"expected ReturnCode 1 with StatusReason {code}, got HTTP {status} {answer}")
    if any(e["kind"] in ("ledger", "giro") for e in events):
        problems.append("something was booked although the payment was rejected")
    if code == "XACC":
        pushes = [e for e in events if e["app"] == "DESP" and e["direction"] == "sent" and (e["path"] or "").endswith("/status")]
        if [e["to"] for e in pushes] != ["PSP A"] or pushes[0]["body"]["paymentTransactionStatus"]["status"] != "Rejected":
            problems.append(f"expected one Rejected status push to PSP A only, got {[(e['to'], e['body']) for e in pushes]}")
    problems += compare_state(after, *seed_expectation())
    print(f"   {why}")
    print(f"   The app got ReturnCode {answer.get('ReturnCode') if answer else '?'}, StatusReason {answer.get('StatusReason') if answer else '?'}. Nothing changed:")
    print_balances(after)
    return problems


# ---------------------------------------------------------------- regression checks

def example_body(folder, prefix):
    f = sorted(glob.glob(os.path.join(EX, folder, f"[0-9][0-9]-{prefix}*.json")))[0]
    return json.load(open(f, encoding="utf-8"))


def no_leftovers(st):
    problems = []
    for dean, c in st["customers"].items():
        if c["giroBlocked"]:
            problems.append(f"{dean}: {c['giroBlocked']} still blocked on the giro account")
    if st["pending"]:
        problems.append(f"{st['pending']} transaction(s) still pending at the banks")
    for psp in ("PSP A", "PSP B"):
        for c in get(psp, "/sim/state")["customers"]:
            if D(c.get("reservedOutgoing", 0)) or D(c.get("pendingIncoming", 0)):
                problems.append(f"{c['name']}: reservations left (out {c['reservedOutgoing']}, in {c['pendingIncoming']})")
    return problems


def check_parallel_holding_limit():
    """Review item 2: two parallel 50 EUR payments to Ben (balance 80, limit 100) must not take him over 100."""
    print("\n── regression: two parallel payments to Ben, holding limit 100 EUR")
    reset_all()
    ben = TD["users"]["ben"]
    http("POST", URL["PSP B"] + "/sim/holding-limit", {"command": "SET_HOLDING_LIMIT", "amount": {"currency": "EUR", "amount": "100.00"}})
    step = example_body("p2p-two-psps", "app-payment-initiation")
    answers = [None, None]

    def pay(i, payer):
        body = dict(step["body"], MessageIdentification=f"E2E-PAR-{i}")
        answers[i] = http("POST", I1_URL["PSP A"] + "/i1/messages", body, {"Sim-User-DEAN": TD["users"][payer]["dean"]})

    try:
        threads = [threading.Thread(target=pay, args=(i, who)) for i, who in enumerate(("anna", "clara"))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        settle_down()
    finally:
        http("POST", URL["PSP B"] + "/sim/holding-limit", {"command": "SET_HOLDING_LIMIT", "amount": {"currency": "EUR", "amount": TD["holdingLimit"]}})
    st = snapshot()
    problems = [f"payment {i}: {a}" for i, a in enumerate(answers) if a[0] != 200 or a[1].get("ReturnCode") != 0]
    ben_de, ben_giro = st["entries"][ben["entry"]], st["customers"][ben["dean"]]["giro"]
    if ben_de > D("100.00"):
        problems.append(f"Ben holds {ben_de} digital euro, above the limit of 100.00")
    if ben_de + ben_giro != D(ben["balance"]) + D(ben["giro"]) + 100:
        problems.append(f"Ben's money does not add up: {ben_de} + {ben_giro}")
    problems += no_leftovers(st)
    if not st["money_ok"]:
        problems.append(f"money check failed: {st['money']}")
    print(f"   Both payments answered {[a[1].get('ReturnCode') for a in answers]}; Ben has {ben_de} digital euro and {ben_giro} on his giro account.")
    return problems


def check_self_payment():
    """Review item 4: the DESP rejects debtorEntry == creditorEntry in its 201."""
    print("\n── regression: payment instruction to the same ledger entry")
    reset_all()
    step = example_body("p2p-same-psp", "desp-post-payment-instructions")
    body = json.loads(json.dumps(step["body"]))
    body["paymentIdentification"]["UETR"] = "01a19bc1-0000-7000-8000-" + os.urandom(6).hex()
    body["paymentInstructionObject"]["creditorEntry"] = body["paymentInstructionObject"]["debtorEntry"]
    headers = dict(step["http"]["headers"], **{"Request-Id": str(__import__("uuid").uuid4())})
    status, answer = http("POST", URL["DESP"] + "/v1/payment-instructions", body, headers)
    time.sleep(0.3)
    problems = []
    if status != 201 or answer["paymentTransactionStatus"]["status"] != "Rejected" or answer["statusReason"]["statusReasonCode"] != "XACC":
        problems.append(f"expected 201 Rejected XACC, got {status} {answer}")
    problems += compare_state(snapshot(), *seed_expectation())
    print(f"   DESP answered {status} {answer.get('paymentTransactionStatus')} {answer.get('statusReason', {}).get('statusReasonCode')}.")
    return problems


def check_desp_down(procs, log_dir, run_local):
    """Review item 1: if the DESP cannot be reached, the giro block is released (XNET)."""
    print("\n── regression: Clara funds 200 EUR while the DESP is down")
    reset_all()
    step = example_body("funding-same-psp", "app-funding-request")
    desp = [p for p in procs if p.sim_name == "DESP"]
    run_local.stop_all(desp)
    try:
        status, answer = send_i1(step)
        clara = next(c for c in get("PSP A", "/sim/state")["customers"] if c["name"] == "Clara Weber")
    finally:
        run_local.restart(procs, "DESP", log_dir)
    problems = []
    if status != 200 or answer.get("ReturnCode") != 1 or answer.get("StatusReason") != "XNET":
        problems.append(f"expected ReturnCode 1 XNET, got HTTP {status} {answer}")
    if D(clara["giroBlocked"]) or D(clara["giro"]) != D(TD["users"]["clara"]["giro"]) or D(clara.get("pendingIncoming", 0)):
        problems.append(f"Clara's giro not restored: {clara}")
    reset_all()
    print(f"   The app got StatusReason {answer.get('StatusReason')}; Clara's giro {clara['giro']}, blocked {clara['giroBlocked']}.")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--start", action="store_true", help="start the apps (tools/run_local.py) and stop them afterwards")
    ap.add_argument("--via-relay", action="store_true",
                    help="send all traffic through the network relay (no delay), as in the control room; "
                         "with --start the relay is started too")
    args = ap.parse_args()
    if args.via_relay:
        I1_URL.update(RELAY_I1)
    procs = []
    if args.start:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import run_local
        if args.via_relay:
            run_local.use_relay("play", "0")
        log_dir = tempfile.mkdtemp(prefix="desim-e2e-")
        procs = run_local.start_all(log_dir)
        print(f"Started {', '.join(p.sim_name for p in procs)} (logs in {log_dir})")
    elif apps_up():
        raise SystemExit(f"{apps_up()} is not running. Start the apps with  python3 tools/run_local.py  or use --start.")
    elif args.via_relay:
        try:
            urllib.request.urlopen("http://127.0.0.1:8100/health", timeout=2).close()
        except (urllib.error.URLError, OSError):
            raise SystemExit("The relay is not running. Start  python3 tools/run_local.py --control-room  or use --start.")
    results = []
    try:
        for folder in FLOWS:
            results.append((folder, run_flow(folder)))
        for r in REJECTIONS:
            results.append(("rejection " + r[4], run_rejection(*r)))
        results.append(("regression: parallel payments vs holding limit", check_parallel_holding_limit()))
        results.append(("regression: payment to the same ledger entry", check_self_payment()))
        if procs:
            results.append(("regression: giro block released when DESP is down", check_desp_down(procs, log_dir, run_local)))
        else:
            print("\n── regression 'DESP down' skipped: needs --start")
        reset_all()
    finally:
        if procs:
            run_local.stop_all(procs)
    print("\n══ Summary")
    failed = 0
    for name, problems in results:
        print(f"   {'PASS' if not problems else 'FAIL'}  {name}")
        for p in problems:
            print(f"         - {p}")
        failed += bool(problems)
    print(f"   {len(results) - failed} of {len(results)} passed.")
    if procs and not failed:
        shutil.rmtree(log_dir, ignore_errors=True)  # keep the logs only when something failed
    elif procs:
        print(f"   App logs: {log_dir}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

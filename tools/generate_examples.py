#!/usr/bin/env python3
"""Generate the example message sequences in /examples from fictional test data.

Deterministic: running it twice produces identical files. Every value is
fictional. Field names follow the ECB annexes; see contracts/INTERPRETATION.md
for the choices made where the spec is open.
"""
import base64
import hashlib
import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "examples")
T0 = datetime(2026, 11, 2, 10, 15, 0, tzinfo=timezone.utc)

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def dean(serial: int, business: bool = False) -> str:
    """Build a DEAN with valid MOD 97-10 check digits (computed like an IBAN)."""
    bban = ("1" if business else "0") + f"{serial:013d}"
    rearranged = bban + "EU00"
    num = int("".join(str(ord(c) - 55) if c.isalpha() else c for c in rearranged))
    return f"EU{98 - num % 97:02d}{bban}"


def _rand(seed: str, n: int) -> bytes:
    return hashlib.sha256(seed.encode()).digest()[:n]


def uuid7(seed: str, at: datetime) -> str:
    ms = int(at.timestamp() * 1000)
    r = bytearray(_rand(seed, 10))
    b = ms.to_bytes(6, "big") + bytes([0x70 | (r[0] & 0x0F), r[1]]) + bytes([0x80 | (r[2] & 0x3F)]) + bytes(r[3:10])
    h = b.hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def uuid4(seed: str) -> str:
    r = bytearray(_rand("v4" + seed, 16))
    r[6] = 0x40 | (r[6] & 0x0F)
    r[8] = 0x80 | (r[8] & 0x3F)
    h = r.hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def entry_id(seed: str) -> str:
    return "ENT-" + hashlib.sha256(("entry" + seed).encode()).hexdigest()[:12].upper()


def sim_encrypt(obj: dict) -> str:
    """SIMULATED encryption: base64 of the JSON. Deliberately not secure."""
    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()
    return "SIMENC:" + base64.b64encode(raw).decode()


def ts(at: datetime) -> str:
    return at.strftime("%Y-%m-%dT%H:%M:%S.") + f"{at.microsecond // 1000:03d}Z"


def amt(x) -> dict:
    return {"currency": "EUR", "amount": f"{Decimal(x):.2f}"}


def status(code: str) -> dict:
    return {"status": code}


# --------------------------------------------------------------------------
# test data
# --------------------------------------------------------------------------

BANKS = {
    "A": {"name": "PSP A (fictional retail bank)", "bic": "SIMADEF0XXX"},
    "B": {"name": "PSP B (fictional bank + acquiring)", "bic": "SIMBDEF0XXX"},
}
USERS = {
    "anna": {"name": "Anna Schmidt", "bank": "A", "dean": dean(1), "phone": "+4915100000001", "balance": "120.00", "giro": "2500.00"},
    "clara": {"name": "Clara Weber", "bank": "A", "dean": dean(2), "phone": "+4915100000002", "balance": "40.00", "giro": "900.00"},
    "ben": {"name": "Ben Müller", "bank": "B", "dean": dean(3), "phone": "+4915100000003", "balance": "80.00", "giro": "1700.00"},
}
for k, u in USERS.items():
    u["entry"] = entry_id(k)
HOLDING_LIMIT = "3000.00"  # placeholder, ADR 0005
DCA = {"A": "1000000.00", "B": "1000000.00"}

NODES = {"appA": "Banking App A", "appB": "Banking App B", "A": "PSP A", "B": "PSP B", "DESP": "DESP", "ledger": "DESP ledger", "giroA": "PSP A core banking"}


class Seq:
    def __init__(self, folder, title, summary):
        self.folder, self.title, self.summary = folder, title, summary
        self.steps, self.t, self.n = [], T0, 0

    def tick(self, ms=180):
        self.t += timedelta(milliseconds=ms)
        return self.t

    def add(self, **kw):
        kw = {"step": self.n, **kw}
        self.steps.append(kw)
        self.n += 1
        return kw

    def write(self):
        d = os.path.join(OUT, self.folder)
        os.makedirs(d, exist_ok=True)
        index = []
        for s in self.steps:
            slug = s.pop("_slug")
            fn = f"{s['step']:02d}-{slug}.json"
            with open(os.path.join(d, fn), "w") as f:
                json.dump(s, f, indent=2, ensure_ascii=False)
                f.write("\n")
            index.append((s["step"], s["from"], s["to"], s["title"], fn, s.get("placeholder", False)))
        with open(os.path.join(d, "README.md"), "w") as f:
            f.write(f"# {self.title}\n\n{self.summary}\n\n| Step | From → to | What | File |\n|---|---|---|---|\n")
            for n, fr, to, title, fn, ph in index:
                f.write(f"| {n} | {fr} → {to} | {title}{' *(placeholder)*' if ph else ''} | [{fn}]({fn}) |\n")


def hdr_req(seq, rid, requesting_bic=None):
    h = {"Content-Type": "application/json", "Request-Id": rid, "Request-Timestamp": ts(seq.t)}
    if requesting_bic:
        h["Requesting-Agent"] = requesting_bic
    return h


def hdr_resp(seq, rid):
    return {"Content-Type": "application/json", "Request-Id": rid, "Response-Timestamp": ts(seq.t)}


# --------------------------------------------------------------------------
# building blocks
# --------------------------------------------------------------------------

def app_initiation(seq, payer, payee, amount, text):
    p, q = USERS[payer], USERS[payee]
    seq.tick(0)
    mid = f"APP{p['bank']}-{seq.folder[:10].upper()}-0001"
    body = {
        "MessageIdentification": mid,
        "EventIdentification": "Individual user payment initiation",
        "CreationDateTime": ts(seq.t),
        "PaymentMethod": "ALIA",
        "TransactionType": "PP01",
        "Amount": float(amount),
        "Currency": "EUR",
        "TransactionDate": ts(seq.t),
        "ProxyAccount": q["phone"],
        "ProxyAccountType": "TELE",
        "MerchantCategoryCode": "4829",
        "UnstructuredRemittanceInformation": text,
    }
    seq.add(_slug="app-payment-initiation", title=f"{p['name'].split()[0]} asks her bank to pay {q['name'].split()[0]} {amount} EUR",
            **{"from": f"Banking App {p['bank']}", "to": NODES[p["bank"]]}, interface="I1",
            specRef="Annex D1-1 §8.1.1.6, p.103–106",
            schema="contracts/i1-app-psp/schemas/payment-initiation.request.schema.json",
            http={"method": "POST", "path": "/i1/messages", "headers": {"Content-Type": "application/json"}},
            body=body,
            explanation="The app sends the payment by phone number (alias). The transport (POST /i1/messages) is our choice; the message content follows D1-1.")
    return mid


def alias_lookup(seq, payer, payee):
    p, q = USERS[payer], USERS[payee]
    seq.tick()
    seq.add(_slug="alias-lookup", title=f"Which bank serves {q['phone']}?", placeholder=True,
            **{"from": NODES[p["bank"]], "to": "DESP"}, interface="I3 (placeholder)",
            specRef="Rulebook §4.4.3 p.99 (Alias Lookup Service). Message not specified in the documents available.",
            body={"request": {"proxyAlias": q["phone"], "proxyAliasType": "TELE"},
                  "response": {"DEAN": q["dean"], "digitalEuroPspId": BANKS[q["bank"]]["bic"]}},
            explanation="PLACEHOLDER. The payer's bank resolves the alias to the payee's DEAN and bank. The real call is in an ECB document we do not have; field names borrowed from the D2-6 account data query.")


def giro_step(seq, user, action, amount, slug, title):
    u = USERS[user]
    seq.tick(60)
    seq.add(_slug=slug, title=title, **{"from": NODES[u["bank"]], "to": f"PSP {u['bank']} core banking"}, interface="I5 (ours)",
            specRef="Rulebook LM-030 (reverse waterfall); D1-1 §7.2 non-digital euro payment account funds management service (funds blocking, debit)",
            body={"action": action, "account": f"giro of {u['name']}", "amount": amt(amount)},
            explanation="Bank-internal step on the giro account. Not part of the ECB messages; shown so the money trail is complete.")


def ledger_step(seq, title, moves, note):
    seq.tick(250)
    seq.add(_slug="ledger-settlement", title=title, **{"from": "DESP", "to": "DESP ledger"}, interface="internal",
            specRef="Annex D2-7 p.10 (atomic settlement)",
            body={"settlementDateTime": ts(seq.t), "bookings": moves},
            explanation=note)
    return ts(seq.t)


# --------------------------------------------------------------------------
# scenario 1: same bank
# --------------------------------------------------------------------------

def scenario_same_psp():
    s = Seq("p2p-same-psp", "Anna pays Clara 25 EUR (same bank)",
            "Both users bank with PSP A, so the central platform settles directly (Annex D2-7 Fig. 5). No encrypted part is sent: in the payment messages DESP receives no names and no DEANs, only ledger entries, bank codes and the amount. (The alias lookup in step 1 is a separate service of the platform.)")
    A, C = USERS["anna"], USERS["clara"]
    bic = BANKS["A"]["bic"]
    mid = app_initiation(s, "anna", "clara", "25.00", "Cinema tickets")
    alias_lookup(s, "anna", "clara")
    uetr = uuid7("same-uetr", s.tick())
    rid = uuid4("same-r1")
    accept = ts(s.t)
    s.add(_slug="desp-post-payment-instructions", title="Payment instruction to the central platform",
          **{"from": "PSP A", "to": "DESP"}, interface="I3",
          specRef="Annex D2-7 DESP API POST /payment-instructions, p.57–62",
          schema="contracts/i3-psp-desp/schemas/desp-api/post-payment-instructions.request.schema.json",
          http={"method": "POST", "path": "/v1/payment-instructions", "headers": hdr_req(s, rid, bic)},
          body={"acceptanceDateTime": accept, "paymentIdentification": {"UETR": uetr},
                "paymentInstructionObject": {"debtorAgent": {"bicfi": bic}, "creditorAgent": {"bicfi": bic}, "paymentType": "PP01",
                                             "amount": amt("25.00"), "debtorEntry": {"entryId": A["entry"]}, "creditorEntry": {"entryId": C["entry"]}}},
          explanation="Same bank: PSP A sends both ledger entries in clear text and no encrypted part.")
    piid = uuid4("same-piid")
    s.tick(40)
    s.add(_slug="desp-response-201", title="Received and technically valid",
          **{"from": "DESP", "to": "PSP A"}, interface="I3", specRef="Annex D2-7 p.62–64",
          schema="contracts/i3-psp-desp/schemas/desp-api/post-payment-instructions.response-201.schema.json",
          http={"status": 201, "headers": hdr_resp(s, rid)},
          body={"paymentIdentification": {"UETR": uetr}, "paymentInstructionId": piid, "paymentTransactionStatus": status("AcceptedTechnicalValidation")},
          explanation="The 201 only confirms receipt. The final result comes later as a status push.")
    sdt = ledger_step(s, "Settle: Anna −25, Clara +25", [
        {"entry": A["entry"], "owner_for_observer": "Anna (PSP A)", "before": A["balance"], "change": "-25.00", "after": "95.00"},
        {"entry": C["entry"], "owner_for_observer": "Clara (PSP A)", "before": C["balance"], "change": "+25.00", "after": "65.00"}],
        "Both bookings happen in one step. The ledger knows entries, not names; 'owner_for_observer' is added only for the audience.")
    rid2 = uuid4("same-r2")
    s.tick(30)
    s.add(_slug="psp-api-status-push", title="Final status: settled",
          **{"from": "DESP", "to": "PSP A"}, interface="I3", specRef="Annex D2-7 PSP API POST /payment-instructions/{id}/status, p.106–109",
          schema="contracts/i3-psp-desp/schemas/psp-api/post-payment-instruction-status.request.schema.json",
          http={"method": "POST", "path": f"/v1/payment-instructions/{piid}/status", "headers": hdr_req(s, rid2)},
          body={"paymentIdentification": {"UETR": uetr}, "settlementDateTime": sdt, "settlementBusinessDay": "2026-11-02",
                "paymentTransactionStatus": status("AcceptedSettlementCompletedDebitorAccount")},
          explanation="DESP pushes the final status to the bank.")
    s.tick(20)
    s.add(_slug="psp-api-204", title="Status received", **{"from": "PSP A", "to": "DESP"}, interface="I3", specRef="Annex D2-7 p.106–109",
          http={"status": 204, "headers": {"Request-Id": rid2, "Response-Timestamp": ts(s.t)}}, body=None,
          explanation="204: no body.")
    s.tick(60)
    s.add(_slug="app-response", title="Anna's app shows: paid", **{"from": "PSP A", "to": "Banking App A"}, interface="I1",
          specRef="Annex D1-1 common outgoing envelope", schema="contracts/i1-app-psp/schemas/response.schema.json",
          http={"status": 200, "headers": {"Content-Type": "application/json"}},
          body={"MessageIdentification": "PSPA-RESP-0001", "OriginalMessageIdentification": mid, "CreationDateTime": ts(s.t), "ReturnCode": 0},
          explanation="ReturnCode 0 = successful. Answering after the final status is our choice.")
    s.write()


# --------------------------------------------------------------------------
# scenario 2: two banks
# --------------------------------------------------------------------------

def scenario_two_psps():
    s = Seq("p2p-two-psps", "Anna (PSP A) pays Ben (PSP B) 50 EUR",
            "Payer-initiated payment between two banks (Annex D2-7 Fig. 7). DESP forwards the instruction to PSP B, which adds Ben's ledger entry, then settles and pushes the status to both banks. Ben's DEAN and both names travel encrypted for PSP B; in the payment messages DESP only sees bank codes, amount, payment type and entries.")
    A, Bn = USERS["anna"], USERS["ben"]
    ba, bb = BANKS["A"]["bic"], BANKS["B"]["bic"]
    mid = app_initiation(s, "anna", "ben", "50.00", "Concert ticket")
    alias_lookup(s, "anna", "ben")
    uetr = uuid7("two-uetr", s.tick())
    accept = ts(s.t)
    secret = {"creditorAccount": {"DEAN": Bn["dean"]}, "creditor": {"name": Bn["name"]},
              "debtorAccount": {"DEAN": A["dean"]}, "debtor": {"name": A["name"]},
              "remittanceInformationUnstructured": "Concert ticket", "transactionAmount": amt("50.00")}
    enc = sim_encrypt(secret)
    rid = uuid4("two-r1")
    s.add(_slug="desp-post-payment-instructions", title="Payment instruction to the central platform",
          **{"from": "PSP A", "to": "DESP"}, interface="I3", specRef="Annex D2-7 p.57–62",
          schema="contracts/i3-psp-desp/schemas/desp-api/post-payment-instructions.request.schema.json",
          http={"method": "POST", "path": "/v1/payment-instructions", "headers": hdr_req(s, rid, ba)},
          body={"acceptanceDateTime": accept, "paymentIdentification": {"UETR": uetr},
                "paymentInstructionObject": {"debtorAgent": {"bicfi": ba}, "creditorAgent": {"bicfi": bb}, "paymentType": "PP01",
                                             "amount": amt("50.00"), "debtorEntry": {"entryId": A["entry"]},
                                             "encryptedPaymentInstructionObject": enc}},
          decryptedView={"field": "paymentInstructionObject.encryptedPaymentInstructionObject",
                         "schema": "contracts/i3-psp-desp/schemas/encrypted-payment-instruction-content.schema.json", "content": secret},
          explanation="Different banks: no creditorEntry yet (PSP B will add it), and the party details are encrypted for PSP B.")
    piid = uuid4("two-piid")
    s.tick(40)
    s.add(_slug="desp-response-201", title="Received and technically valid", **{"from": "DESP", "to": "PSP A"}, interface="I3",
          specRef="Annex D2-7 p.62–64", schema="contracts/i3-psp-desp/schemas/desp-api/post-payment-instructions.response-201.schema.json",
          http={"status": 201, "headers": hdr_resp(s, rid)},
          body={"paymentIdentification": {"UETR": uetr}, "paymentInstructionId": piid, "paymentTransactionStatus": status("AcceptedTechnicalValidation")},
          explanation="Receipt only. Settlement waits for PSP B.")
    rid3 = uuid4("two-r3")
    s.tick(30)
    s.add(_slug="psp-api-forward-to-payee-bank", title="Forwarded to Ben's bank", **{"from": "DESP", "to": "PSP B"}, interface="I3",
          specRef="Annex D2-7 PSP API POST /payment-instructions, p.102–104",
          schema="contracts/i3-psp-desp/schemas/psp-api/post-payment-instructions.request.schema.json",
          http={"method": "POST", "path": "/v1/payment-instructions", "headers": hdr_req(s, rid3)},
          body={"acceptanceDateTime": accept, "paymentIdentification": {"UETR": uetr},
                "paymentInstructionObject": {"paymentInstructionId": piid, "debtorAgent": {"bicfi": ba}, "creditorAgent": {"bicfi": bb},
                                             "paymentType": "PP01", "amount": amt("50.00"), "encryptedPaymentInstructionObject": enc}},
          decryptedView={"field": "paymentInstructionObject.encryptedPaymentInstructionObject",
                         "schema": "contracts/i3-psp-desp/schemas/encrypted-payment-instruction-content.schema.json", "content": secret},
          explanation="Anna's ledger entry is removed before forwarding (D2-7 p.103). PSP B decrypts the party details to find Ben's account.")
    s.tick(90)
    s.add(_slug="psp-api-response-201", title="PSP B accepts and adds Ben's ledger entry", **{"from": "PSP B", "to": "DESP"}, interface="I3",
          specRef="Annex D2-7 p.104–105", schema="contracts/i3-psp-desp/schemas/psp-api/post-payment-instructions.response-201.schema.json",
          http={"status": 201, "headers": hdr_resp(s, rid3)},
          body={"paymentIdentification": {"UETR": uetr}, "paymentTransactionStatus": status("AcceptedCustomerProfile"),
                "paymentInstructionObject": {"creditorEntry": {"entryId": Bn["entry"]}}},
          explanation=f"Ben's account is active and 80 + 50 = 130 EUR stays below the holding limit ({HOLDING_LIMIT} EUR), so no waterfall is needed.")
    sdt = ledger_step(s, "Settle: Anna −50, Ben +50", [
        {"entry": A["entry"], "owner_for_observer": "Anna (PSP A)", "before": A["balance"], "change": "-50.00", "after": "70.00"},
        {"entry": Bn["entry"], "owner_for_observer": "Ben (PSP B)", "before": Bn["balance"], "change": "+50.00", "after": "130.00"}],
        "One atomic booking across both banks' customers. No money moves between the banks: both balances live on the same ECB ledger.")
    push = {"paymentIdentification": {"UETR": uetr}, "settlementDateTime": sdt, "settlementBusinessDay": "2026-11-02",
            "paymentTransactionStatus": status("AcceptedSettlementCompletedDebitorAccount")}
    for bank, slug in (("A", "psp-api-status-push-payer-bank"), ("B", "psp-api-status-push-payee-bank")):
        r = uuid4("two-push" + bank)
        s.tick(15)
        s.add(_slug=slug, title=f"Final status to PSP {bank}: settled", **{"from": "DESP", "to": f"PSP {bank}"}, interface="I3",
              specRef="Annex D2-7 p.106–109", schema="contracts/i3-psp-desp/schemas/psp-api/post-payment-instruction-status.request.schema.json",
              http={"method": "POST", "path": f"/v1/payment-instructions/{piid}/status", "headers": hdr_req(s, r)}, body=push,
              explanation="DESP sends the status to both banks at the same time.")
        s.tick(10)
        s.add(_slug=f"psp-api-204-psp-{bank.lower()}", title="Status received", **{"from": f"PSP {bank}", "to": "DESP"}, interface="I3",
              specRef="Annex D2-7 p.106–109", http={"status": 204, "headers": {"Request-Id": r, "Response-Timestamp": ts(s.t)}}, body=None,
              explanation="204: no body.")
    s.tick(60)
    s.add(_slug="app-response", title="Anna's app shows: paid", **{"from": "PSP A", "to": "Banking App A"}, interface="I1",
          specRef="Annex D1-1 common outgoing envelope", schema="contracts/i1-app-psp/schemas/response.schema.json",
          http={"status": 200, "headers": {"Content-Type": "application/json"}},
          body={"MessageIdentification": "PSPA-RESP-0002", "OriginalMessageIdentification": mid, "CreationDateTime": ts(s.t), "ReturnCode": 0},
          explanation="How PSP B notifies Ben's app is not specified in the documents we have.")
    s.write()


# --------------------------------------------------------------------------
# scenario 3: same bank with reverse waterfall
# --------------------------------------------------------------------------

def scenario_reverse_waterfall():
    s = Seq("p2p-reverse-waterfall-same-psp", "Anna pays Clara 150 EUR with only 120 EUR on her account",
            "Reverse waterfall at the same bank (Annex D2-7 Fig. 11). The missing 30 EUR are taken from Anna's giro account and turned into digital euro in the same atomic step as the payment. The bank's central bank money account (DCA) pays for the new digital euro.")
    A, C = USERS["anna"], USERS["clara"]
    bic = BANKS["A"]["bic"]
    amount, missing = Decimal("150.00"), Decimal("150.00") - Decimal(A["balance"])
    mid = app_initiation(s, "anna", "clara", "150.00", "Weekend trip share")
    alias_lookup(s, "anna", "clara")
    giro_step(s, "anna", "block", missing, "giro-block", f"Block {missing} EUR on Anna's giro account")
    uetr = uuid7("rw-uetr", s.tick())
    rid = uuid4("rw-r1")
    s.add(_slug="desp-post-payment-instructions", title="Payment instruction with funding part", **{"from": "PSP A", "to": "DESP"}, interface="I3",
          specRef="Annex D2-7 p.57–62 (fundingObject p.61)", schema="contracts/i3-psp-desp/schemas/desp-api/post-payment-instructions.request.schema.json",
          http={"method": "POST", "path": "/v1/payment-instructions", "headers": hdr_req(s, rid, bic)},
          body={"acceptanceDateTime": ts(s.t), "paymentIdentification": {"UETR": uetr},
                "paymentInstructionObject": {"debtorAgent": {"bicfi": bic}, "creditorAgent": {"bicfi": bic}, "paymentType": "PP01", "amount": amt(amount),
                                             "debtorEntry": {"entryId": A["entry"]}, "creditorEntry": {"entryId": C["entry"]}},
                "fundingObject": {"instructedAgent": {"bicfi": bic}, "amount": amt(missing)}},
          explanation=f"Funding amount = payment − balance = 150.00 − {A['balance']} = {missing} (rulebook LM-030-002). The giro account is at the same bank, so no encrypted funding part is needed.")
    piid, fid = uuid4("rw-piid"), uuid4("rw-fid")
    s.tick(40)
    s.add(_slug="desp-response-201", title="Received: payment and funding technically valid", **{"from": "DESP", "to": "PSP A"}, interface="I3",
          specRef="Annex D2-7 p.62–64", schema="contracts/i3-psp-desp/schemas/desp-api/post-payment-instructions.response-201.schema.json",
          http={"status": 201, "headers": hdr_resp(s, rid)},
          body={"paymentIdentification": {"UETR": uetr}, "paymentInstructionId": piid, "paymentTransactionStatus": status("AcceptedTechnicalValidation"),
                "fundingId": fid, "fundingStatus": status("AcceptedTechnicalValidation")},
          explanation="Payment and funding get separate IDs but will be settled together.")
    sdt = ledger_step(s, "Settle: DCA A −30, Anna +30 −150, Clara +150", [
        {"entry": "DCA of PSP A", "owner_for_observer": "PSP A central bank money", "before": DCA["A"], "change": f"-{missing}", "after": f"{Decimal(DCA['A']) - missing:.2f}"},
        {"entry": A["entry"], "owner_for_observer": "Anna (PSP A)", "before": A["balance"], "change": f"+{missing} -150.00", "after": "0.00"},
        {"entry": C["entry"], "owner_for_observer": "Clara (PSP A)", "before": C["balance"], "change": "+150.00", "after": "190.00"}],
        "All three bookings happen atomically: either everything or nothing. 30 EUR of new digital euro are issued against PSP A's DCA. Which DCA is used is not named in any message (our reading: the instructed agent's).")
    rid2 = uuid4("rw-r2")
    s.tick(30)
    s.add(_slug="psp-api-status-push", title="Final status: payment and funding settled", **{"from": "DESP", "to": "PSP A"}, interface="I3",
          specRef="Annex D2-7 p.106–109", schema="contracts/i3-psp-desp/schemas/psp-api/post-payment-instruction-status.request.schema.json",
          http={"method": "POST", "path": f"/v1/payment-instructions/{piid}/status", "headers": hdr_req(s, rid2)},
          body={"paymentIdentification": {"UETR": uetr}, "settlementDateTime": sdt, "settlementBusinessDay": "2026-11-02",
                "paymentTransactionStatus": status("AcceptedSettlementCompletedDebitorAccount"),
                "fundingStatus": status("AcceptedSettlementCompletedDebitorAccount"), "fundingId": fid},
          explanation="One status push covers both parts.")
    s.tick(20)
    s.add(_slug="psp-api-204", title="Status received", **{"from": "PSP A", "to": "DESP"}, interface="I3", specRef="Annex D2-7 p.106–109",
          http={"status": 204, "headers": {"Request-Id": rid2, "Response-Timestamp": ts(s.t)}}, body=None, explanation="204: no body.")
    giro_step(s, "anna", "debit blocked amount", missing, "giro-debit", f"Debit {missing} EUR from Anna's giro account")
    s.tick(60)
    s.add(_slug="app-response", title="Anna's app shows: paid, 30 EUR topped up from giro", **{"from": "PSP A", "to": "Banking App A"}, interface="I1",
          specRef="Annex D1-1 common outgoing envelope", schema="contracts/i1-app-psp/schemas/response.schema.json",
          http={"status": 200, "headers": {"Content-Type": "application/json"}},
          body={"MessageIdentification": "PSPA-RESP-0003", "OriginalMessageIdentification": mid, "CreationDateTime": ts(s.t), "ReturnCode": 0},
          explanation="Anna's giro account: 2500.00 → 2470.00. Her digital euro balance: 0.00.")
    s.write()


def main():
    if os.path.isdir(OUT):
        for name in os.listdir(OUT):
            p = os.path.join(OUT, name)
            if os.path.isdir(p):
                shutil.rmtree(p)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "test-data.json"), "w") as f:
        json.dump({"_note": "All fictional. Generated by tools/generate_examples.py.", "holdingLimit": HOLDING_LIMIT,
                   "banks": BANKS, "dcaBalances": DCA, "users": USERS}, f, indent=2, ensure_ascii=False)
        f.write("\n")
    scenario_same_psp()
    scenario_two_psps()
    scenario_reverse_waterfall()
    print("examples written to", OUT)


if __name__ == "__main__":
    main()

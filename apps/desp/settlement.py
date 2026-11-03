"""Settlement engine of the DESP (Annex D2-7).

Pattern (contracts/i3-psp-desp/README.md, catalogue §1.4):
  1. a bank sends an instruction; the DESP answers 201 at once
     (AcceptedTechnicalValidation, or Rejected after the checks in INTERPRETATION T11);
  2. in the background: if the payee is at another bank, forward the instruction
     to that bank's PSP API and collect its part (creditorEntry, maybe a
     paymentDefundingObject);
  3. settle all legs in one atomic step (ledger.settle);
  4. push the final status to every bank involved; each answers 204.
"""
import asyncio
from collections import deque

import httpx

import sim_log
from http_util import call, request_headers
from reasons import AB03, D005, XACC, XDUP, XFMT, XFWD, XINT, XNSU, Rejection
from sim_ids import business_day, money, now_ts, uuid4

S = "i3-psp-desp/schemas/"
SETTLED = "AcceptedSettlementCompletedDebitorAccount"
ACCEPTED = "AcceptedTechnicalValidation"


class Engine:
    def __init__(self, ledger, participants, schemas):
        self.ledger, self.participants, self.schemas = ledger, participants, schemas
        self.client: httpx.AsyncClient | None = None  # set at start-up (app.py)
        self.used_uetrs: set[str] = set()
        self.transactions: deque = deque(maxlen=200)
        self._tasks: set = set()

    def reset(self):
        self.used_uetrs.clear()
        self.transactions.clear()

    # ------------------------------------------------------------------ helpers

    def spawn(self, coro):
        """Run work after the 201 has been sent (keeps a reference so it is not garbage-collected)."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _check_amount(self, amount_obj: dict, what: str):
        if amount_obj["currency"] != "EUR" or money(amount_obj["amount"]) <= 0:
            raise Rejection(XFMT, f"{what}: amount must be a positive EUR amount")

    def _check_uetr(self, body: dict):
        if body["paymentIdentification"]["UETR"] in self.used_uetrs:
            raise Rejection(XDUP)

    def _record(self, kind, uetr, ident, status, reason=None):
        self.transactions.append({"time": now_ts(), "type": kind, "UETR": uetr, "id": ident, "status": status,
                                  "statusReason": reason})

    def _book(self, uetr: str, legs: list) -> str:
        """Atomic settlement + one log event shaped like examples/*-ledger-settlement.json."""
        bookings = self.ledger.settle(legs)
        for b in bookings:  # label DCAs as in /examples ("DCA of PSP B"); user entries stay anonymous
            if b["entry"].startswith("DCA of "):
                b["entry"] = "DCA of " + self.participants.name(b["entry"][len("DCA of "):])
        sdt = now_ts()
        sim_log.emit("internal", "DESP", "DESP ledger", "internal", kind="ledger",
                     body={"UETR": uetr, "settlementDateTime": sdt, "bookings": bookings},
                     note="settled: " + ", ".join(f"{b['entry']} {b['change']}" for b in bookings))
        return sdt

    async def _push(self, bic: str, path: str, body: dict, schema: str):
        """Status push to a bank's PSP API (D2-7 p.95–109); the bank answers 204 without body."""
        self.schemas.check_outgoing(S + schema, body)
        try:
            status, _, _ = await call(self.client, "DESP", self.participants.name(bic), "POST",
                                      self.participants.url(bic), path, body, request_headers())
        except httpx.HTTPError:
            return  # already logged by call(); the spec has no retry rule (catalogue §1.5)
        if status != 204:
            sim_log.emit("internal", "DESP", "DESP", "internal", kind="note",
                         note=f"{self.participants.name(bic)} answered {status} to {path}, expected 204")

    # ------------------------------------------------------------------ payment instructions

    def accept_payment_instruction(self, agent: str, body: dict) -> dict:
        """Technical validation (T11) and the 201 body. Starts the background processing when accepted."""
        pio = body["paymentInstructionObject"]
        uetr = body["paymentIdentification"]["UETR"]
        piid = uuid4()
        try:
            self._validate_payment_instruction(agent, body)
        except Rejection as r:
            # Fig. 6: rejected at technical validation; no status push follows, nothing to query (fn 20)
            self._record("payment instruction", uetr, piid, "Rejected", r.code)
            return {"paymentIdentification": {"UETR": uetr}, "paymentInstructionId": piid,
                    "paymentTransactionStatus": {"status": "Rejected"}, "statusReason": r.reason()}
        self.used_uetrs.add(uetr)
        resp = {"paymentIdentification": {"UETR": uetr}, "paymentInstructionId": piid,
                "paymentTransactionStatus": {"status": ACCEPTED}}
        fid = did = None
        if "fundingObject" in body:      # reverse waterfall (D2-7 p.61)
            fid = uuid4()
            resp.update({"fundingId": fid, "fundingStatus": {"status": ACCEPTED}})
        if "defundingObject" in body:    # waterfall, same bank only (D2-7 p.61)
            did = uuid4()
            resp.update({"defundingId": did, "defundingStatus": {"status": ACCEPTED}})
        self._record("payment instruction", uetr, piid, ACCEPTED)
        self.spawn(self._process_payment(body, piid, fid, did))
        return resp

    def _validate_payment_instruction(self, agent: str, body: dict):
        pio = body["paymentInstructionObject"]
        debtor, creditor = pio["debtorAgent"]["bicfi"], pio["creditorAgent"]["bicfi"]
        # D005 first: an unknown requesting bank learns that it is not a participant
        for bic in (agent, debtor, creditor):
            if not self.participants.is_participant(bic):
                raise Rejection(D005, f"{bic} is not a participant")
        if agent != debtor:
            raise Rejection(XFMT, "Requesting-Agent must be the debtorAgent")
        self._check_amount(pio["amount"], "payment")
        same = debtor == creditor
        if same and pio.get("creditorEntry") == pio["debtorEntry"]:
            raise Rejection(XACC, "Payer and payee are the same ledger entry")
        # D2-7 p.59: creditorEntry mandatory at the same bank; encrypted part only between different banks
        if same and "creditorEntry" not in pio:
            raise Rejection(XFMT, "creditorEntry is mandatory when both users are at the same bank")
        if same and "encryptedPaymentInstructionObject" in pio:
            raise Rejection(XFMT, "No encrypted part at the same bank (data minimisation, D2-7 p.15)")
        if not same and "encryptedPaymentInstructionObject" not in pio:
            raise Rejection(XFMT, "encryptedPaymentInstructionObject is mandatory between different banks")
        if not same and "creditorEntry" in pio:
            raise Rejection(XFMT, "creditorEntry comes from the payee bank when the banks differ")
        if not same and "defundingObject" in body:
            raise Rejection(XFMT, "defundingObject only when payer and payee share a bank; else the payee bank adds it")
        fo, do = body.get("fundingObject"), body.get("defundingObject")
        if fo:
            self._check_amount(fo["amount"], "funding")
            if fo["instructedAgent"]["bicfi"] != debtor:  # ADR 0001: giro account always at the same bank
                raise Rejection(XNSU, "Open funding is not supported (ADR 0001)")
        if do:
            self._check_amount(do["amount"], "defunding")
            if do["instructedAgent"]["bicfi"] != creditor:
                raise Rejection(XNSU, "Open defunding is not supported (ADR 0001)")
        self._check_uetr(body)

    async def _process_payment(self, body: dict, piid: str, fid, did):
        pio = body["paymentInstructionObject"]
        uetr = body["paymentIdentification"]["UETR"]
        debtor, creditor = pio["debtorAgent"]["bicfi"], pio["creditorAgent"]["bicfi"]
        debtor_entry = pio["debtorEntry"]["entryId"]
        creditor_entry = (pio.get("creditorEntry") or {}).get("entryId")
        defunding = body.get("defundingObject")
        notify = [debtor]
        ok, reason, sdt = False, None, None
        try:
            if debtor != creditor:
                notify.append(creditor)
                creditor_entry, defunding = await self._forward_payment(body, piid)
                if defunding:
                    did = uuid4()
            self.ledger.check_entry(debtor_entry, debtor)
            self.ledger.check_entry(creditor_entry, creditor)
            # T4: funding debits the DCA of instructedAgent, defunding credits it.
            legs = []
            if body.get("fundingObject"):
                fo = body["fundingObject"]
                legs.append(("funding", f"dca:{fo['instructedAgent']['bicfi']}", f"entry:{debtor_entry}", money(fo["amount"]["amount"])))
            legs.append(("payment", f"entry:{debtor_entry}", f"entry:{creditor_entry}", money(pio["amount"]["amount"])))
            if defunding:
                legs.append(("defunding", f"entry:{creditor_entry}", f"dca:{defunding['instructedAgent']['bicfi']}", money(defunding["amount"]["amount"])))
            sdt = self._book(uetr, legs)
            ok = True
        except Rejection as r:
            reason = r.reason()
            if r.payee_rejected and creditor in notify:
                notify.remove(creditor)  # Fig. 8: the payee bank rejected, only the payer bank gets a status
        except Exception as e:  # a bug: still tell the banks, never leave them waiting
            sim_log.emit("internal", "DESP", "DESP", "internal", kind="note", note=f"ERROR in settlement: {e!r}")
            reason = Rejection(XINT).reason()
        self._record("payment instruction", uetr, piid, SETTLED if ok else "Rejected", None if ok else reason["statusReasonCode"])

        def status_for(bic):
            b = {"paymentIdentification": {"UETR": uetr}}
            if ok:
                b.update({"settlementDateTime": sdt, "settlementBusinessDay": business_day()})
            b["paymentTransactionStatus"] = {"status": SETTLED if ok else "Rejected"}
            # D2-7 p.16: funding ID/status only to the payer side, defunding ID/status only to the payee side (T7)
            if bic == debtor and fid:
                b.update({"fundingStatus": {"status": SETTLED if ok else "Rejected"}, "fundingId": fid})
            if bic == creditor and did:
                b.update({"defundingStatus": {"status": SETTLED if ok else "Rejected"}, "defundingId": did})
            if not ok:
                b["statusReason"] = reason
            return b

        # "simultaneously" (D2-7 Fig. 7): payer bank first, payee bank right after
        await asyncio.gather(*(self._push(bic, f"/v1/payment-instructions/{piid}/status", status_for(bic),
                                          "psp-api/post-payment-instruction-status.request.schema.json") for bic in notify))

    async def _forward_payment(self, body: dict, piid: str):
        """PSP API POST /v1/payment-instructions to the payee bank (D2-7 p.102–106).
        The payer's ledger entry is NOT forwarded (p.103). Returns (creditorEntry, paymentDefundingObject or None)."""
        pio = body["paymentInstructionObject"]
        creditor = pio["creditorAgent"]["bicfi"]
        fwd = {"acceptanceDateTime": body["acceptanceDateTime"], "paymentIdentification": body["paymentIdentification"],
               "paymentInstructionObject": {"paymentInstructionId": piid, "debtorAgent": pio["debtorAgent"],
                                            "creditorAgent": pio["creditorAgent"], "paymentType": pio["paymentType"],
                                            "amount": pio["amount"],
                                            "encryptedPaymentInstructionObject": pio["encryptedPaymentInstructionObject"]}}
        self.schemas.check_outgoing(S + "psp-api/post-payment-instructions.request.schema.json", fwd)
        try:
            status, _, resp = await call(self.client, "DESP", self.participants.name(creditor), "POST",
                                         self.participants.url(creditor), "/v1/payment-instructions", fwd, request_headers())
        except httpx.TimeoutException:
            raise Rejection(AB03)
        except httpx.HTTPError:
            raise Rejection(AB03, "Payee bank not reachable")
        errors = self.schemas.errors(S + "psp-api/post-payment-instructions.response-201.schema.json", resp) if status == 201 else []
        if status != 201 or errors:
            raise Rejection(XFWD, f"Payee bank answered HTTP {status}" + (f": {errors[0]['detail']}" if errors else ""))
        if resp["paymentIdentification"]["UETR"] != body["paymentIdentification"]["UETR"]:
            raise Rejection(XFWD, "Payee bank answered with another UETR")
        if resp["paymentTransactionStatus"]["status"] == "Rejected":
            r = resp["statusReason"]
            raise Rejection(r["statusReasonCode"], r.get("statusReasonAdditionalInformation"), payee_rejected=True)
        pdo = resp.get("paymentDefundingObject")
        if pdo:
            self._check_amount(pdo["amount"], "defunding")
            if pdo["instructedAgent"]["bicfi"] != creditor:
                raise Rejection(XNSU, "Open defunding is not supported (ADR 0001)")
        return resp["paymentInstructionObject"]["creditorEntry"]["entryId"], pdo

    # ------------------------------------------------------------------ standalone funding / defunding

    def accept_funding(self, kind: str, agent: str, body: dict) -> dict:
        """kind 'funding' or 'defunding' (D2-7 Fig. 1 / Fig. 3). Returns the 201 body."""
        obj = body[f"{kind}Object"]
        uetr = body["paymentIdentification"]["UETR"]
        try:
            bic = obj["instructingAgent"]["bicfi"]
            for b in (agent, bic):  # D005 first, as for payment instructions
                if not self.participants.is_participant(b):
                    raise Rejection(D005, f"{b} is not a participant")
            if agent != bic:
                raise Rejection(XFMT, "Requesting-Agent must be the instructingAgent")
            if obj["instructedAgent"]["bicfi"] != bic:
                raise Rejection(XNSU, f"Open {kind} is not supported (ADR 0001)")
            self._check_amount(obj["amount"], kind)
            self._check_uetr(body)
        except Rejection as r:
            self._record(kind, uetr, None, "Rejected", r.code)
            # T9: no fundingId/defundingId when rejected
            return {"paymentIdentification": {"UETR": uetr}, f"{kind}TransactionStatus": {"status": "Rejected"},
                    "statusReason": r.reason()}
        self.used_uetrs.add(uetr)
        ident = uuid4()
        self._record(kind, uetr, ident, ACCEPTED)  # T8
        self.spawn(self._process_funding(kind, body, ident))
        return {"paymentIdentification": {"UETR": uetr}, f"{kind}Id": ident,
                f"{kind}TransactionStatus": {"status": ACCEPTED}}

    async def _process_funding(self, kind: str, body: dict, ident: str):
        obj = body[f"{kind}Object"]
        uetr = body["paymentIdentification"]["UETR"]
        bic, entry = obj["instructingAgent"]["bicfi"], obj["userEntry"]["entryId"]
        dca = obj["instructedAgent"]["bicfi"]  # T4
        amount = money(obj["amount"]["amount"])
        ok, reason, sdt = False, None, None
        try:
            self.ledger.check_entry(entry, bic)
            leg = (f"dca:{dca}", f"entry:{entry}") if kind == "funding" else (f"entry:{entry}", f"dca:{dca}")
            sdt = self._book(uetr, [(kind, *leg, amount)])
            ok = True
        except Rejection as r:
            reason = r.reason()
        except Exception as e:
            sim_log.emit("internal", "DESP", "DESP", "internal", kind="note", note=f"ERROR in settlement: {e!r}")
            reason = Rejection(XINT).reason()
        self._record(kind, uetr, ident, SETTLED if ok else "Rejected", None if ok else reason["statusReasonCode"])
        push = {"paymentIdentification": {"UETR": uetr}, f"{kind}TransactionStatus": {"status": SETTLED if ok else "Rejected"}}
        if ok:
            push.update({"settlementDateTime": sdt, "settlementBusinessDay": business_day()})
        else:
            push["statusReason"] = reason
        await self._push(bic, f"/v1/{kind}s/{ident}/status", push, f"psp-api/post-{kind}-status.request.schema.json")

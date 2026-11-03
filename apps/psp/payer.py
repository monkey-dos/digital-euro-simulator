"""What the bank does when its own customer asks for something over I1
(Annex D1-1): pay someone, fund, defund.

Each flow builds the I3 message for the DESP exactly like the matching
scenario in /examples, registers what the final status means for this bank
(Pending.register, before sending), sends, and waits for the final status
(INTERPRETATION A7). A business problem raises Rejection, which the I1
handler turns into ReturnCode 1 + StatusReason (A13).
"""
from decimal import Decimal

import sim_log
from reasons import XACC, XBAL, XFMT, XLIM, XNSU, XTMO, Rejection
from sim_ids import amount_obj, fmt, money, now_ts, sim_encrypt, uuid7

SETTLED = "AcceptedSettlementCompletedDebitorAccount"
P2P_MCC = "4829"  # D1-1: merchant category code for P2P


class PayerSide:
    def __init__(self, cfg: dict, bank, desp, pending, status_timeout: float):
        self.cfg, self.bank, self.desp, self.pending = cfg, bank, desp, pending
        self.bic, self.me = cfg["bic"], cfg["name"]
        self.holding_limit = money(cfg["holdingLimit"])
        self.status_timeout = status_timeout

    def note(self, text: str):
        sim_log.emit("internal", self.me, self.me, "internal", kind="note", note=text)

    async def _send_and_wait(self, uetr: str, on_final, send, accepted) -> None:
        """Register first (an early status push must not be lost), send, then wait for the final status."""
        fut = self.pending.register(uetr, on_final)
        try:
            resp = await send()
        except Exception:
            self.pending.cancel(uetr)
            raise
        status, reason = accepted(resp)
        if status == "Rejected":
            # Fig. 6: rejected at technical validation, no status push will come
            self.pending.cancel(uetr)
            on_final({"rejectedIn201": True, "statusReason": reason})
            raise Rejection(reason["statusReasonCode"], reason.get("statusReasonAdditionalInformation"))
        push = await self.pending.wait(fut, self.status_timeout)
        if push is None:
            raise Rejection(XTMO)  # the record stays: a late status push is still booked
        final = next(v["status"] for k, v in push.items() if k.endswith("TransactionStatus"))
        if final != SETTLED:
            r = push.get("statusReason") or {}
            raise Rejection(r.get("statusReasonCode", XFMT), r.get("statusReasonAdditionalInformation"))

    # ---------------------------------------------------------------- payment (D1-1 §8.1.1.6)

    async def payment(self, payer, msg: dict) -> None:
        if msg["TransactionType"] != "PP01" or msg["MerchantCategoryCode"] != P2P_MCC:
            raise Rejection(XNSU, "Only P2P payments (PP01, MCC 4829) so far")
        if msg["Currency"] != "EUR":
            raise Rejection(XFMT, "Currency must be EUR")
        amount = money(msg["Amount"])

        # 1. who is the payee? (alias lookup is a PLACEHOLDER call, INTERPRETATION T5)
        if msg["PaymentMethod"] == "ALIA":
            if not msg.get("ProxyAccount") or not msg.get("ProxyAccountType"):
                raise Rejection(XFMT, "ProxyAccount and ProxyAccountType are needed for an alias payment")
            payee_dean, payee_bic = await self.desp.alias_lookup(msg["ProxyAccount"], msg["ProxyAccountType"])
        elif msg["PaymentMethod"] == "DEAN":
            if not msg.get("PayeeDEAN") or not msg.get("CreditorAgent"):
                raise Rejection(XFMT, "PayeeDEAN and CreditorAgent are needed for a DEAN payment")
            payee_dean, payee_bic = msg["PayeeDEAN"], msg["CreditorAgent"]
        else:
            raise Rejection(XNSU, f"Payment method {msg['PaymentMethod']} is not built yet")
        if payee_dean == payer.dean:
            raise Rejection(XACC, "Payer and payee are the same account")
        same_bank = payee_bic == self.bic
        payee = self.bank.customer(payee_dean) if same_bank else None

        # 2. balance check; reverse waterfall if the digital euro balance is too low
        #    (rulebook LM-030-002; assumed enabled for every test user, see README)
        missing = max(amount - payer.balance, Decimal("0"))
        if missing:
            self.note(f"{payer.name}: {fmt(payer.balance)} on digital euro, {fmt(amount)} needed → reverse waterfall {fmt(missing)}")
            try:
                self.bank.block(payer, missing)  # A11: block before sending to the DESP
            except Rejection:
                raise Rejection(XBAL, f"Digital euro {fmt(payer.balance)} + giro {fmt(payer.giro - payer.blocked)} < {fmt(amount)}")

        # 3. waterfall at the same bank: we are also the payee bank (D2-7 p.61 defundingObject)
        excess = Decimal("0")
        if same_bank:
            excess = max(payee.balance + amount - self.holding_limit, Decimal("0"))

        # 4. the payment instruction (D2-7 p.57–62), same shape as /examples
        uetr = uuid7()  # C5
        pio = {"debtorAgent": {"bicfi": self.bic}, "creditorAgent": {"bicfi": payee_bic}, "paymentType": "PP01",
               "amount": amount_obj(amount), "debtorEntry": {"entryId": payer.entry}}
        if same_bank:
            pio["creditorEntry"] = {"entryId": payee.entry}  # both entries in clear, no encrypted part
        else:
            secret = {"creditorAccount": {"DEAN": payee_dean}}
            if msg.get("Name"):
                secret["creditor"] = {"name": msg["Name"]}  # A14: as typed by the user, not checked
            secret.update({"debtorAccount": {"DEAN": payer.dean}, "debtor": {"name": payer.name}})
            if msg.get("UnstructuredRemittanceInformation"):
                secret["remittanceInformationUnstructured"] = msg["UnstructuredRemittanceInformation"]
            if msg.get("EndToEndId"):
                secret["paymentIdentification"] = {"endToEndId": msg["EndToEndId"]}
            secret["transactionAmount"] = amount_obj(amount)
            self.desp.schemas.check_outgoing("i3-psp-desp/schemas/encrypted-payment-instruction-content.schema.json", secret)
            pio["encryptedPaymentInstructionObject"] = sim_encrypt(secret)  # C7
        body = {"acceptanceDateTime": now_ts(), "paymentIdentification": {"UETR": uetr}, "paymentInstructionObject": pio}
        if missing:
            body["fundingObject"] = {"instructedAgent": {"bicfi": self.bic}, "amount": amount_obj(missing)}  # T3: no encrypted part
        if excess:
            body["defundingObject"] = {"instructedAgent": {"bicfi": self.bic}, "amount": amount_obj(excess)}

        def on_final(push):
            if push.get("paymentTransactionStatus", {}).get("status") != SETTLED:
                if missing:
                    self.bank.release(payer, missing)
                return
            # A11: debit the blocked giro amount after the settled status
            if missing:
                self.bank.debit_blocked(payer, missing)
            payer.balance += missing - amount
            if same_bank:
                payee.balance += amount - excess
                if excess:
                    self.bank.credit(payee, excess)  # A11: waterfall credit after the settled status

        await self._send_and_wait(uetr, on_final, lambda: self.desp.post_payment_instruction(body),
                                  lambda r: (r["paymentTransactionStatus"]["status"], r.get("statusReason")))

    # ---------------------------------------------------------------- funding / defunding (D1-1 §7.1.1.1)

    async def funding(self, user, msg: dict) -> None:
        funding = msg["RequestType"] == "ONLF"
        kind = "funding" if funding else "defunding"
        amount = money(msg["Amount"])
        dean = msg.get("DigitalEuroAccountNumber", user.dean)
        giro_side, deur_side = (msg["DebtorAccount"], msg["CreditorAccount"]) if funding else (msg["CreditorAccount"], msg["DebtorAccount"])
        if dean != user.dean or deur_side != user.dean or giro_side != user.iban:
            raise Rejection(XACC, "Accounts in the request do not belong to the logged-in user")
        if msg.get("DebtorAgent") or msg.get("CreditorAgent"):
            raise Rejection(XNSU, "Giro account at another bank is not supported (ADR 0001)")
        if funding:
            if user.balance + amount > self.holding_limit:
                raise Rejection(XLIM, f"{fmt(user.balance)} + {fmt(amount)} > holding limit {fmt(self.holding_limit)}")
            self.bank.block(user, amount)  # A11: block before sending
        elif user.balance < amount:
            raise Rejection(XBAL, f"Digital euro balance {fmt(user.balance)} < {fmt(amount)}")

        uetr = uuid7()
        body = {"acceptanceDateTime": now_ts(), "paymentIdentification": {"UETR": uetr},
                f"{kind}Object": {"instructingAgent": {"bicfi": self.bic}, "instructedAgent": {"bicfi": self.bic},
                                  "amount": amount_obj(amount), "userEntry": {"entryId": user.entry},
                                  "paymentType": "FU01" if funding else "DF01"}}

        def on_final(push):
            settled = push.get(f"{kind}TransactionStatus", {}).get("status") == SETTLED
            if funding:
                if settled:
                    self.bank.debit_blocked(user, amount)  # A11: debit after the settled status
                    user.balance += amount
                else:
                    self.bank.release(user, amount)
            elif settled:
                user.balance -= amount
                self.bank.credit(user, amount)  # A11: credit after the settled status

        await self._send_and_wait(uetr, on_final, lambda: self.desp.post_funding(kind, body),
                                  lambda r: (r[f"{kind}TransactionStatus"]["status"], r.get("statusReason")))

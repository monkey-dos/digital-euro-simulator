"""What the bank does when the DESP forwards a payment to one of its customers
(PSP API POST /v1/payment-instructions, Annex D2-7 p.102–106).

The bank decrypts the party details (simulated, INTERPRETATION C7), finds its
customer by DEAN, checks the holding limit and answers in the 201:
  - AcceptedCustomerProfile + creditorEntry, and
  - a paymentDefundingObject if the customer would exceed the holding limit
    (waterfall, rulebook LM-050-002: amount = balance + payment − limit).
It then waits for the DESP's final status push (no I1 call involved) and books
the waterfall credit on the giro account after the settled status (A11).
"""
from decimal import Decimal

import sim_log
from reasons import XACC, XFMT, Rejection, status_reason
from sim_ids import amount_obj, fmt, money, sim_decrypt

ENC_SCHEMA = "i3-psp-desp/schemas/encrypted-payment-instruction-content.schema.json"
SETTLED = "AcceptedSettlementCompletedDebitorAccount"


class PayeeSide:
    def __init__(self, cfg: dict, bank, pending, schemas, payer_side):
        self.bic, self.me = cfg["bic"], cfg["name"]
        self.bank, self.pending, self.schemas = bank, pending, schemas
        self.payer_side = payer_side  # holds the current holding limit

    def answer_forwarded(self, body: dict) -> dict:
        """Returns the 201 body for a forwarded payment instruction."""
        uetr = body["paymentIdentification"]["UETR"]
        try:
            payee, amount = self._payee_of(body)
            limit = self.payer_side.holding_limit
            excess = max(payee.balance + amount - limit, Decimal("0"))
        except Rejection as r:
            return {"paymentIdentification": {"UETR": uetr}, "paymentTransactionStatus": {"status": "Rejected"},
                    "statusReason": status_reason(r.code, r.info)}
        resp = {"paymentIdentification": {"UETR": uetr}, "paymentTransactionStatus": {"status": "AcceptedCustomerProfile"},
                "paymentInstructionObject": {"creditorEntry": {"entryId": payee.entry}}}
        if excess:
            sim_log.emit("internal", self.me, self.me, "internal", kind="note",
                         note=f"{payee.name}: {fmt(payee.balance)} + {fmt(amount)} > limit {fmt(limit)} → waterfall {fmt(excess)}")
            # ADR 0001: the giro account is at this bank, so instructedAgent = own BIC and no encrypted part
            resp["paymentDefundingObject"] = {"instructedAgent": {"bicfi": self.bic}, "amount": amount_obj(excess)}

        def on_final(push):
            if push.get("paymentTransactionStatus", {}).get("status") != SETTLED:
                return
            payee.balance += amount - excess
            if excess:
                self.bank.credit(payee, excess)  # A11: credit after the settled status

        self.pending.register(uetr, on_final)
        return resp

    def _payee_of(self, body: dict):
        pio = body["paymentInstructionObject"]
        if pio["creditorAgent"]["bicfi"] != self.bic:
            raise Rejection(XACC, "This bank is not the creditorAgent")
        try:
            secret = sim_decrypt(pio["encryptedPaymentInstructionObject"])
        except ValueError:
            raise Rejection(XFMT, "Encrypted part cannot be decrypted")
        errors = self.schemas.errors(ENC_SCHEMA, secret)
        if errors:
            raise Rejection(XFMT, f"Encrypted part: {errors[0]['detail']}")
        dean = secret["creditorAccount"].get("DEAN")
        if not dean:
            raise Rejection(XACC, "creditorAccount must be a DEAN")
        amount = money(pio["amount"]["amount"])
        if money(secret["transactionAmount"]["amount"]) != amount:
            raise Rejection(XFMT, "transactionAmount differs from amount")
        return self.bank.customer(dean), amount

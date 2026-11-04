"""The bank's small Helicopter Money ledger (ADR 0002, simulation only).

Helicopter Money is new money made by the game master, impossible with the real
digital euro. The bank sees two kinds, both for a customer:
  - "digital-euro": the DESP put new digital euro on the customer's ledger entry.
    The bank only updates its copy of the balance. No giro account, no DCA.
  - "giro": the DESP credited new central bank money to this bank's DCA. The
    bank books  "DCA at the central bank +X / giro of <customer> +X"  and
    credits the customer's giro account. The digital euro balance stays.

The banks do not keep a full balance sheet in this simulation. This ledger
covers only Helicopter Money, so the observer can check: giro Helicopter Money
credited to customers = the DCA increase the bank was told about.
"""
from decimal import Decimal

import sim_log
from reasons import XACC, Rejection
from sim_ids import fmt, now_ts


class HelicopterLedger:
    def __init__(self, me: str):
        self.me = me
        self.bookings: list[dict] = []

    def clear(self):
        self.bookings = []

    def total(self, account: str) -> Decimal:
        return sum((Decimal(b["amount"]) for b in self.bookings if b["account"] == account), Decimal("0"))

    def state(self) -> dict:
        giro, dca = self.total("giro"), self.total("giro")  # one booking has both legs: DCA +X and giro +X
        return {"giro": fmt(giro), "digitalEuro": fmt(self.total("digital-euro")), "dcaReceived": fmt(dca),
                "ok": giro == dca, "bookings": list(self.bookings)}

    def book_giro(self, bank, customer, amount: Decimal, hid: str):
        """Giro Helicopter Money: bank ledger booking, then the customer's giro credit."""
        legs = [{"account": "DCA at the central bank", "change": f"+{fmt(amount)}"},
                {"account": f"giro of {customer.name}", "change": f"+{fmt(amount)}"}]
        sim_log.emit("internal", self.me, f"{self.me} bank ledger", "I5 (ours)", kind="bank-ledger",
                     body={"helicopterMoney": True, "helicopterId": hid, "bookings": legs},
                     note=f"bank ledger (Helicopter Money): DCA at the central bank +{fmt(amount)} / giro of {customer.name} +{fmt(amount)}")
        bank.credit(customer, amount, label="credit (Helicopter Money)")
        self.bookings.append({"helicopterId": hid, "time": now_ts(), "account": "giro", "dean": customer.dean,
                              "name": customer.name, "amount": fmt(amount)})

    def book_digital_euro(self, customer, amount: Decimal, hid: str):
        """Digital euro Helicopter Money: only the bank's copy of the balance changes."""
        customer.balance += amount
        sim_log.emit("internal", self.me, self.me, "I5 (ours)", kind="note",
                     note=f"digital euro Helicopter Money: balance of {customer.name} +{fmt(amount)} → {fmt(customer.balance)} (copy of the DESP ledger)")
        self.bookings.append({"helicopterId": hid, "time": now_ts(), "account": "digital-euro", "dean": customer.dean,
                              "name": customer.name, "amount": fmt(amount)})

    def reverse(self, bank, hid: str):
        """Undo a booking (the DESP side could not be completed or was undone)."""
        b = next((x for x in self.bookings if x["helicopterId"] == hid), None)
        if b is None:
            raise Rejection(XACC, f"No Helicopter Money booking {hid}")
        c = bank.customer(b["dean"])
        amount = Decimal(b["amount"])
        if b["account"] == "giro":
            if c.giro - c.blocked < amount:
                raise ValueError("The giro money is already spent")
            bank.debit_giro(c, amount, label="undo credit (Helicopter Money)")
        else:
            if c.balance - c.reserved_out < amount:
                raise ValueError("The digital euro is already spent")
            c.balance -= amount
            sim_log.emit("internal", self.me, self.me, "I5 (ours)", kind="note",
                         note=f"digital euro Helicopter Money undone: balance of {c.name} -{fmt(amount)} → {fmt(c.balance)}")
        self.bookings.remove(b)

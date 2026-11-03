"""The bank's customers and its core banking stand-in (giro accounts, interface I5).

Per customer the bank knows: name, DEAN, phone alias, ledger entry, IBAN, the
giro account balance and the amount blocked on it, and the digital euro balance
as the bank sees it (updated when the DESP reports a settlement). The real
digital euro balance lives only on the DESP ledger; the bank's copy is what it
uses for the balance and holding-limit checks.

Giro operations follow INTERPRETATION A11: funding blocks before sending to the
DESP and debits after the settled status (released on rejection); defunding and
waterfall credit after the settled status. Every giro step is logged as an
internal event shaped like the giro steps in /examples.
"""
from decimal import Decimal

import sim_log
from reasons import XACC, XBAL, Rejection
from sim_ids import amount_obj, fmt, money


class Customer:
    def __init__(self, name, dean, phone, entry, iban, giro, balance):
        self.name, self.dean, self.phone, self.entry, self.iban = name, dean, phone, entry, iban
        self.giro, self.blocked, self.balance = money(giro), Decimal("0.00"), money(balance)
        # Amounts of transactions still waiting for their final status. Taken into account
        # by every new check, so parallel payments cannot overspend or exceed the holding limit.
        self.reserved_out = Decimal("0.00")  # will leave the digital euro balance
        self.pending_in = Decimal("0.00")    # will arrive on the digital euro balance

    def spendable(self) -> Decimal:
        """Digital euro the customer can still spend now."""
        return self.balance - self.reserved_out

    def projected(self) -> Decimal:
        """Highest balance the customer may reach once pending transactions settle (holding-limit check)."""
        return self.balance + self.pending_in

    def view(self) -> dict:
        return {"name": self.name, "DEAN": self.dean, "phone": self.phone, "entryId": self.entry, "iban": self.iban,
                "giro": fmt(self.giro), "giroBlocked": fmt(self.blocked), "giroAvailable": fmt(self.giro - self.blocked),
                "digitalEuro": fmt(self.balance), "reservedOutgoing": fmt(self.reserved_out),
                "pendingIncoming": fmt(self.pending_in)}


class Bank:
    def __init__(self, me: str):
        self.me = me  # e.g. "PSP A", used in log events
        self.by_dean: dict[str, Customer] = {}

    def seed(self, users: dict, bank_key: str):
        self.by_dean = {u["dean"]: Customer(u["name"], u["dean"], u["phone"], u["entry"], u["iban"], u["giro"], u["balance"])
                        for u in users.values() if u["bank"] == bank_key}

    def customer(self, dean: str) -> Customer:
        c = self.by_dean.get(dean)
        if c is None:
            raise Rejection(XACC, "No digital euro account with this DEAN at this bank")
        return c

    # ---------------------------------------------------------------- core banking (I5, ours)

    def _giro_event(self, c: Customer, action: str, amount: Decimal):
        sim_log.emit("internal", self.me, f"{self.me} core banking", "I5 (ours)", kind="giro",
                     body={"action": action, "account": f"giro of {c.name}", "amount": amount_obj(amount)},
                     note=f"giro of {c.name}: {action} {fmt(amount)} → giro {fmt(c.giro)}, blocked {fmt(c.blocked)}")

    @staticmethod
    def check_giro(c: Customer, amount: Decimal):
        if c.giro - c.blocked < amount:
            raise Rejection(XBAL, f"Giro account: {fmt(c.giro - c.blocked)} available, {fmt(amount)} needed")

    def block(self, c: Customer, amount: Decimal):
        self.check_giro(c, amount)
        c.blocked += amount
        self._giro_event(c, "block", amount)

    def debit_blocked(self, c: Customer, amount: Decimal):
        c.blocked -= amount
        c.giro -= amount
        self._giro_event(c, "debit blocked amount", amount)

    def release(self, c: Customer, amount: Decimal):
        c.blocked -= amount
        self._giro_event(c, "release", amount)

    def credit(self, c: Customer, amount: Decimal):
        c.giro += amount
        self._giro_event(c, "credit", amount)

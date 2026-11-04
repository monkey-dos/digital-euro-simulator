"""Central ledger of the DESP: one balance per ledger entry, one DCA per bank.

D2-7 p.10 fn 4: user holdings and DCAs are both "entries" in the same settlement
ledger. The ledger holds no names and no DEANs; each user entry only records
which bank (BIC) it is held via. Amounts are Decimal, never float.

settle() books a list of legs all-or-nothing (D2-7 p.10: "either the whole
transaction is settled, or nothing is settled"). It contains no `await`, so in
this single-threaded asyncio app no other settlement can run in between.
"""
from decimal import Decimal

from reasons import XACC, XBAL, XDCA, Rejection
from sim_ids import fmt, money


class Ledger:
    def __init__(self):
        self.entries: dict[str, dict] = {}   # entryId -> {"bic", "balance"}
        self.dca: dict[str, Decimal] = {}    # BIC -> central bank money
        self.opening_entries = Decimal("0")  # seeded digital euro (no DCA counterpart)
        self.opening_dca: dict[str, Decimal] = {}
        # Helicopter Money (ADR 0002): new money made by the game master, counted apart from everything else.
        self.hm_digital_euro = Decimal("0")
        self.hm_dca: dict[str, Decimal] = {}
        self.hm_bookings: dict[str, dict] = {}   # helicopterId -> what was created (kept for the undo)

    def seed(self, entries: dict[str, tuple[str, str]], dca: dict[str, str]):
        """entries: entryId -> (bic, balance); dca: BIC -> balance."""
        self.entries = {e: {"bic": bic, "balance": money(b)} for e, (bic, b) in entries.items()}
        self.dca = {bic: money(b) for bic, b in dca.items()}
        self.opening_entries = sum((e["balance"] for e in self.entries.values()), Decimal("0"))
        self.opening_dca = dict(self.dca)
        self.hm_digital_euro, self.hm_dca, self.hm_bookings = Decimal("0"), {}, {}

    # ---------------------------------------------------------------- Helicopter Money (simulation only)

    def helicopter_entry(self, hid: str, entry_id: str, amount: Decimal) -> list[dict]:
        """New digital euro straight onto a person's ledger entry. No DCA is touched."""
        self._hm_check_new(hid)
        e = self.entries.get(entry_id)
        if e is None:
            raise KeyError(f"Unknown ledger entry {entry_id}")
        before = e["balance"]
        e["balance"] += amount
        self.hm_digital_euro += amount
        self.hm_bookings[hid] = {"target": "entry", "key": entry_id, "amount": amount}
        return [{"entry": entry_id, "before": fmt(before), "change": f"+{fmt(amount)}", "after": fmt(e["balance"])}]

    def helicopter_dca(self, hid: str, bic: str, amount: Decimal) -> list[dict]:
        """New central bank money on a bank's DCA. No digital euro entry is touched."""
        self._hm_check_new(hid)
        if bic not in self.dca:
            raise KeyError(f"Unknown DCA of {bic}")
        before = self.dca[bic]
        self.dca[bic] += amount
        self.hm_dca[bic] = self.hm_dca.get(bic, Decimal("0")) + amount
        self.hm_bookings[hid] = {"target": "dca", "key": bic, "amount": amount}
        return [{"entry": f"DCA of {bic}", "before": fmt(before), "change": f"+{fmt(amount)}", "after": fmt(self.dca[bic])}]

    def helicopter_reverse(self, hid: str) -> list[dict]:
        """Undo one Helicopter Money booking (used when the bank could not follow, so the books never stay unbalanced)."""
        b = self.hm_bookings.get(hid)
        if b is None:
            raise KeyError(f"No Helicopter Money booking {hid}")
        amount, key = b["amount"], b["key"]
        book = self.entries[key]["balance"] if b["target"] == "entry" else self.dca[key]
        if book < amount:
            raise ValueError(f"Cannot undo: only {fmt(book)} left, {fmt(amount)} was created")
        label = key if b["target"] == "entry" else f"DCA of {key}"
        if b["target"] == "entry":
            self.entries[key]["balance"] -= amount
            self.hm_digital_euro -= amount
        else:
            self.dca[key] -= amount
            self.hm_dca[key] -= amount
        del self.hm_bookings[hid]
        return [{"entry": label, "before": fmt(book), "change": f"-{fmt(amount)}", "after": fmt(book - amount)}]

    def _hm_check_new(self, hid: str):
        if hid in self.hm_bookings:
            raise ValueError(f"Helicopter Money booking {hid} exists already")

    def check_entry(self, entry_id: str, bic: str):
        """The entry must exist and be held via the given bank."""
        e = self.entries.get(entry_id)
        if e is None or e["bic"] != bic:
            raise Rejection(XACC, f"Ledger entry {entry_id} is not held via {bic}")

    def settle(self, legs: list[tuple[str, str, str, Decimal]]) -> list[dict]:
        """Book legs atomically. Each leg: (kind, from, to, amount) where from/to is
        'entry:<id>' or 'dca:<BIC>'. Legs are applied in order, so a funding leg
        placed before the payment leg covers it (reverse waterfall).
        Returns booking records (as in examples/*-ledger-settlement.json) or raises Rejection."""
        entries = {k: v["balance"] for k, v in self.entries.items()}
        dca = dict(self.dca)
        before = {}
        changes: dict[str, list[str]] = {}

        def acct(ref):
            kind, key = ref.split(":", 1)
            book = entries if kind == "entry" else dca
            if key not in book:
                raise Rejection(XACC, f"Unknown {kind} {key}")
            before.setdefault(ref, book[key])
            return book, key

        for kind, frm, to, amount in legs:
            src, sk = acct(frm)
            dst, dk = acct(to)
            if src[sk] < amount:
                code = XDCA if frm.startswith("dca:") else XBAL
                raise Rejection(code, f"{kind}: {fmt(src[sk])} available, {fmt(amount)} needed")
            src[sk] -= amount
            dst[dk] += amount
            changes.setdefault(frm, []).append(f"-{fmt(amount)}")
            changes.setdefault(to, []).append(f"+{fmt(amount)}")

        # all legs fine: commit
        for k, v in entries.items():
            self.entries[k]["balance"] = v
        self.dca = dca
        bookings = []
        for ref, b in before.items():
            kind, key = ref.split(":", 1)
            after = entries[key] if kind == "entry" else dca[key]
            label = key if kind == "entry" else f"DCA of {key}"
            bookings.append({"entry": label, "before": fmt(b), "change": " ".join(changes.get(ref, [])), "after": fmt(after)})
        return bookings

    def state(self) -> dict:
        """Ledger snapshot plus the money-in-circulation check (ADR 0002):
        digital euro in circulation = opening balances + net DCA debits since start
        (DCA changes made by Helicopter Money left out) + digital euro Helicopter Money."""
        circulation = sum((e["balance"] for e in self.entries.values()), Decimal("0"))
        net_dca_debits = sum((self.opening_dca[b] - (self.dca.get(b, Decimal("0")) - self.hm_dca.get(b, Decimal("0")))
                              for b in self.opening_dca), Decimal("0"))
        expected = self.opening_entries + net_dca_debits + self.hm_digital_euro
        return {
            "entries": [{"entryId": k, "heldVia": v["bic"], "balance": fmt(v["balance"])} for k, v in sorted(self.entries.items())],
            "dcaBalances": {b: fmt(v) for b, v in sorted(self.dca.items())},
            "moneyCheck": {
                "digitalEuroInCirculation": fmt(circulation),
                "openingBalances": fmt(self.opening_entries),
                "netDcaDebitsSinceStart": fmt(net_dca_debits),
                "helicopterMoneyDigitalEuro": fmt(self.hm_digital_euro),
                "ok": circulation == expected,
                "rule": "digital euro in circulation = opening balances + net DCA debits since start "
                        "(DCA money from Helicopter Money not counted) + digital euro Helicopter Money",
            },
            "helicopterMoney": {"digitalEuro": fmt(self.hm_digital_euro),
                                "dca": {b: fmt(v) for b, v in sorted(self.hm_dca.items()) if v}},
        }

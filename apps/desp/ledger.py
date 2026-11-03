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

    def seed(self, entries: dict[str, tuple[str, str]], dca: dict[str, str]):
        """entries: entryId -> (bic, balance); dca: BIC -> balance."""
        self.entries = {e: {"bic": bic, "balance": money(b)} for e, (bic, b) in entries.items()}
        self.dca = {bic: money(b) for bic, b in dca.items()}
        self.opening_entries = sum((e["balance"] for e in self.entries.values()), Decimal("0"))
        self.opening_dca = dict(self.dca)

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
        digital euro in circulation = opening balances + net DCA debits since start."""
        circulation = sum((e["balance"] for e in self.entries.values()), Decimal("0"))
        net_dca_debits = sum((self.opening_dca[b] - self.dca.get(b, Decimal("0")) for b in self.opening_dca), Decimal("0"))
        expected = self.opening_entries + net_dca_debits
        return {
            "entries": [{"entryId": k, "heldVia": v["bic"], "balance": fmt(v["balance"])} for k, v in sorted(self.entries.items())],
            "dcaBalances": {b: fmt(v) for b, v in sorted(self.dca.items())},
            "moneyCheck": {
                "digitalEuroInCirculation": fmt(circulation),
                "openingBalances": fmt(self.opening_entries),
                "netDcaDebitsSinceStart": fmt(net_dca_debits),
                "ok": circulation == expected,
                "rule": "digital euro in circulation = opening balances + net DCA debits since start",
            },
        }

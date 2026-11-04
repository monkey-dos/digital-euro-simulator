# ADR 0002: A game master may create money ("Helicopter Money")

Status: accepted (1 November 2026), amended (4 November 2026)

## Decision
A game master can create new money for **people** at any time. We call it **Helicopter Money**. There are two kinds, and nothing else:

1. **Digital euro.** New money goes directly onto the person's DEAN ledger entry at the DESP. No bank pays for it, no DCA changes.
2. **Giro money, via the bank.** Booked as in the real world:
   1. the DESP credits new central bank money to the bank's DCA;
   2. the bank is told;
   3. the bank books in its own ledger "DCA at the central bank +X / giro of the person +X" and credits the customer's giro account.

   The digital euro balance stays as it is; the person can fund it afterwards as usual.

There is **no stand-alone DCA top-up** any more (the first version of this decision allowed topping up a DCA, a giro account or a DEAN directly). A DCA grows only as the first step of giro Helicopter Money.

Rules:
- Digital euro Helicopter Money is refused (HTTP 409, plain-English error) if the person would exceed the holding limit (the bank's view: digital euro balance + pending incoming + amount > holding limit, ADR 0005). Giro money does not count against the limit.
- It is refused (409) while a scenario is running or a message waits at the gate, like a change of the holding limit and like a reset.
- The amount is positive, has at most two decimals and is at most 1,000,000.00 EUR.
- A reset brings all Helicopter Money totals back to 0.

## Why
Simulations run dry. Without a way to add money, demos stall. Two kinds, because the real world has two places where new money can appear for a person: central bank money for a bank (which the bank passes on to a customer as giro money) and, only in this simulation, digital euro out of nothing. Keeping the bank's own booking in the second kind shows how a bank would book it.

## Consequences
- Money creation is impossible in reality. Every drop is labelled, logged and totalled separately, so the observer can show the bookkeeping rule:
  - digital euro in circulation = opening balances + net DCA debits since start (DCA changes made by Helicopter Money left out) + digital euro Helicopter Money;
  - for each bank: the central bank money the DESP created on its DCA = the giro Helicopter Money the bank credited to customers.
- The game master (the network relay, ADR 0008) orchestrates a drop and sends its messages through the gate, so slow motion, pause and step apply. The apps get simulation-only `/sim/helicopter-money` endpoints (not ECB). If the bank cannot follow after the DESP booked, the relay undoes the DESP booking.
- The banks keep no full balance sheet. Each bank keeps a small ledger for Helicopter Money only; it is just enough for the check above.
- The control room shows the feature as "Helicopter Money" (violet, a dashed "Game master" node on the map). See `apps/observer/README.md`.

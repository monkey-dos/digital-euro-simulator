# ADR 0001: Giro account always at the same bank

Status: accepted (1 November 2026)

## Decision
A customer's giro (commercial bank money) account is always held at the same bank that provides their digital euro access.

## Why
The rulebook allows the linked account at any PSP, which brings up to four banks into one payment (D2-7 Fig. 13). For teaching, that complexity hides more than it shows.

## Consequences
"Open funding" and "open defunding" never occur. Of the 12 endpoints a bank must offer to the DESP, the two forwarded funding/defunding calls are not needed. Digital euro always sit on the ECB ledger; the bank only provides the interface. Defunding turns digital euro into bank money on the giro account.

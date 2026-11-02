# I1 · Banking app ↔ its bank

Based on ECB Annex D1-1 (Distributing PSP requirements). The screens and branding are in Annex D1-3, which we don't have, so the apps use their own design.

Every app → bank message carries `MessageIdentification`, `EventIdentification` (a fixed event name) and `CreationDateTime`. Every bank → app message carries `MessageIdentification`, optionally `OriginalMessageIdentification`, `CreationDateTime`, `ReturnCode` (0 successful, 1 failure) and, on failure, `StatusReason`.

Covered so far: payment initiation, online funding and defunding request, outgoing envelope.

Defined in D1-1, to be added here next: user registration, alias registration, balance, liquidity settings (waterfall), notification settings, payment request, standing orders, transaction history, offboarding.

Transport and naming choices: `contracts/INTERPRETATION.md`, A1–A8.

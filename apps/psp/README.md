# Bank back-end (PSP)

**Run by:** each bank

**Does:** Customers and KYC (test persons), customer↔DEAN link, balance and holding-limit checks, waterfall / reverse waterfall, payment initiation, giro accounts (core banking stand-in).

**Offers interfaces:** I1 (for its banking app), I3 PSP API (10 endpoints in our setup)

**Uses interfaces:** I3 (DESP API)

One template, run once per bank (PSP A, PSP B, …) with its own configuration.

Status: not started. Build against the contracts in `/contracts`.

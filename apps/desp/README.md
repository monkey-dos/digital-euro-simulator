# Central platform (DESP)

**Run by:** Eurosystem

**Does:** Access management (users, DEANs, aliases), alias lookup, settlement engine, central ledger, DCA simulator. Later: token service, fraud scoring, disputes, data exchange.

**Offers interfaces:** I3 (DESP API, 14 endpoints), I4

**Uses interfaces:** I3 (calls the PSP API of every bank)

The only place digital euro balances live. Holds no names.

Status: not started. Build against the contracts in `/contracts`.

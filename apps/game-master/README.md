# Game master console

**Run by:** simulation layer

**Does:** Speed, pause, single step, reset, scenarios, holding limit and **Helicopter Money** (labelled money creation for people, in two kinds: new digital euro on a person's ledger entry, or new central bank money for a bank that the bank credits as giro money, ADR 0009); later test users.

**Status:** the controls live in the control room (`apps/observer`, served by the network relay); the commands are interface I7, implemented by `apps/network-relay`. See [contracts/i7-game-master](../../contracts/i7-game-master/README.md) and ADR 0008. A separate console app is not needed for now.

Helicopter Money is `POST /control/helicopter-money` (I7). The relay orchestrates it and sends its messages through the gate, so slow motion, pause and step apply; the apps only offer simulation-only `/sim/helicopter-money` endpoints. In the control room: the violet **Helicopter Money** button, then **+ Add money** on a person's tile.

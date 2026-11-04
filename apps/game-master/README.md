# Game master console

**Run by:** simulation layer

**Does:** Speed, pause, single step, reset, scenarios, holding limit; later top-ups (labelled money creation, ADR 0002) and test users.

**Status:** the controls live in the control room (`apps/observer`, served by the network relay); the commands are interface I7, implemented by `apps/network-relay`. See [contracts/i7-game-master](../../contracts/i7-game-master/README.md) and ADR 0008. A separate console app is not needed for now.

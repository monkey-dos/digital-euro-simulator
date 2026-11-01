# Network relay

**Run by:** simulation layer

**Does:** All traffic between apps passes through it. Holds each message for a configurable time (slow motion) and copies it to the observer.

**Offers interfaces:** transparent proxy for I1–I4

**Uses interfaces:** I6 (to observer)

Apps need no changes: they just use the relay's addresses.

Status: not started. Build against the contracts in `/contracts`.

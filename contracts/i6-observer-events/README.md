# I6 – Observer event stream (ours)

Status: draft, to be defined.

Idea: the network relay emits one event per message it forwards, using the same envelope as the files in `/examples` (step, from, to, interface, http, body, decryptedView), plus a timestamp and the relay delay. The DESP additionally emits ledger events (entry, before, after, transaction).

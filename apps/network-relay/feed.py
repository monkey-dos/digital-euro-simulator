"""The control room feed (interface I6, ours): one numbered list of events.

Sources:
  - the relay itself: every message it sees ('message') and the moment it
    lets it continue ('released');
  - the apps' own logs (GET /sim/events): steps that happen inside an app and
    never cross the network, such as the DESP ledger booking or a bank's giro
    block ('internal');
  - the apps' state (GET /sim/state): balances for the money panel ('state');
  - game master actions ('control', 'scenario', 'reset', 'error').

The control room reads the history once (GET /control/history) and then
follows new events live (GET /control/events, server-sent events).
Event shapes: contracts/i6-observer-events/README.md.
"""
import asyncio
import json
from collections import deque
from datetime import datetime, timezone

import httpx


def now_ts() -> str:
    t = datetime.now(timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


class Feed:
    def __init__(self, apps: dict, client: httpx.AsyncClient):
        self.apps = apps                      # relay.json "apps"
        self.client = client
        self.history: deque = deque(maxlen=20000)
        self.seq = 0
        self.listeners: set[asyncio.Queue] = set()
        self._app_seq: dict[str, int] = {}    # last /sim/events seq read per app
        self._poll_lock = asyncio.Lock()
        self._state_task: asyncio.Task | None = None
        self._last_state: str | None = None

    # ---------------------------------------------------------------- publishing

    def publish(self, type_: str, **fields) -> dict:
        self.seq += 1
        event = {"seq": self.seq, "type": type_, "time": now_ts(), **fields}
        self.history.append(event)
        for q in list(self.listeners):
            q.put_nowait(event)
        return event

    def since(self, seq: int) -> list:
        return [e for e in self.history if e["seq"] > seq]

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.listeners.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self.listeners.discard(q)

    def clear(self):
        """After a reset: the old events belong to a world that no longer exists."""
        self.history.clear()

    # ---------------------------------------------------------------- what happens inside the apps

    def _served(self):
        return {slug: a for slug, a in self.apps.items() if a.get("url")}

    async def skip_old_app_events(self):
        """At start-up and after a reset: only events from now on are interesting."""
        for slug, a in self._served().items():
            try:
                r = await self.client.get(a["url"] + "/sim/events", params={"since": 0}, timeout=2)
                events = r.json().get("events", [])
                self._app_seq[slug] = max((e["seq"] for e in events), default=0)
            except (httpx.HTTPError, ValueError):
                self._app_seq[slug] = 0

    async def poll_internal(self):
        """Fetch new inside-the-app steps from every app and publish them in time order.
        Called before each message is shown, so a step that happened before a message
        also appears before it."""
        async with self._poll_lock:
            found = []
            for slug, a in self._served().items():
                try:
                    r = await self.client.get(a["url"] + "/sim/events",
                                              params={"since": self._app_seq.get(slug, 0)}, timeout=2)
                    events = r.json().get("events", [])
                except (httpx.HTTPError, ValueError):
                    continue  # app down or restarting: the relay reports that when a message fails
                for e in events:
                    self._app_seq[slug] = max(self._app_seq.get(slug, 0), e["seq"])
                    if e.get("direction") == "internal":
                        found.append((e.get("time", ""), slug, e))
            for _, slug, e in sorted(found, key=lambda x: (x[0], x[1])):
                self.publish("internal", app=self.apps[slug]["name"], appId=slug, kind=e.get("kind"),
                             **{"from": e.get("from"), "to": e.get("to")}, interface=e.get("interface"),
                             body=e.get("body"), note=e.get("note"), appTime=e.get("time"))

    # ---------------------------------------------------------------- balances

    def refresh_state_soon(self):
        """Fetch balances shortly (several requests in a row cause one refresh)."""
        if self._state_task and not self._state_task.done():
            return
        self._state_task = asyncio.create_task(self._refresh_state(0.15))

    async def _refresh_state(self, wait: float):
        await asyncio.sleep(wait)
        await self.poll_internal()
        state = {}
        for slug, a in self._served().items():
            try:
                r = await self.client.get(a["url"] + "/sim/state", timeout=2)
                state[slug] = r.json()
            except (httpx.HTTPError, ValueError):
                state[slug] = None
        key = json.dumps(state, sort_keys=True, default=str)
        if key != self._last_state:
            self._last_state = key
            self.publish("state", apps=state)

    async def state_now(self) -> dict:
        self._last_state = None
        await self._refresh_state(0)
        return next((e for e in reversed(self.history) if e["type"] == "state"), {})

    async def background_poll(self, every: float = 0.5):
        """Catch inside-the-app steps that no later message reveals (e.g. a giro debit at the very end)."""
        while True:
            await asyncio.sleep(every)
            before = self.seq
            await self.poll_internal()
            if self.seq != before:
                self.refresh_state_soon()

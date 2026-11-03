"""The gate: every message waits here until it may continue.

Two modes (game master command, interface I7):
  play   each message waits `delay` seconds, one after the other (slow motion);
         delay 0 lets everything through at once.
  pause  messages wait until the game master says "step"; each step lets
         exactly one message through.

Messages leave in the order they arrived (first in, first out), so the
control room shows them in a stable order even when two apps talk at once.
The gate only delays: it never changes, drops or reorders the content.
"""
import asyncio
import time


class Gate:
    def __init__(self, mode: str = "play", delay: float = 1.5, on_change=None, on_release=None):
        self.mode = mode
        self.delay = max(0.0, float(delay))
        self.queue: list[tuple[dict, asyncio.Future]] = []
        self._head_since = 0.0           # when the current first message reached the front
        self._steps = 0                  # steps asked for while paused, not yet used
        self._changed = asyncio.Event()  # wakes the release loop
        self._on_change = on_change or (lambda: None)    # called after mode/delay/queue changes
        self._on_release = on_release or (lambda msg: None)
        self._task: asyncio.Task | None = None

    # ---------------------------------------------------------------- control (I7)

    def start(self):
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        if self._task:
            self._task.cancel()

    def set_mode(self, mode: str):
        if mode not in ("play", "pause"):
            raise ValueError("mode must be 'play' or 'pause'")
        if mode != self.mode:
            self.mode = mode
            self._steps = 0
            self._head_since = time.monotonic()  # a message that was paused starts its wait again
            self._wake()

    def set_delay(self, seconds: float):
        seconds = float(seconds)
        if not 0 <= seconds <= 60:
            raise ValueError("delay must be between 0 and 60 seconds")
        self.delay = seconds
        self._wake()

    def step(self) -> bool:
        """Let one message through (only in pause mode). False if nothing is waiting."""
        if self.mode != "pause" or not self.queue:
            return False
        self._steps = 1  # never more than one: a double click must not release two messages
        self._wake()
        return True

    def status(self) -> dict:
        return {"mode": self.mode, "delaySeconds": self.delay, "waiting": len(self.queue),
                "next": self.queue[0][0]["id"] if self.queue else None}

    # ---------------------------------------------------------------- messages

    async def wait_turn(self, msg: dict):
        """Called for every message; returns when the message may continue."""
        fut = asyncio.get_running_loop().create_future()
        if not self.queue:
            self._head_since = time.monotonic()
        self.queue.append((msg, fut))
        self._wake()
        await fut

    def release_all(self):
        """Let everything through at once (used before a reset)."""
        while self.queue:
            self._release_head()

    # ---------------------------------------------------------------- internals

    def _wake(self):
        self._changed.set()
        self._on_change()

    def _release_head(self):
        msg, fut = self.queue.pop(0)
        self._head_since = time.monotonic()
        if not fut.done():
            fut.set_result(None)
        self._on_release(msg)
        self._on_change()

    async def _loop(self):
        while True:
            self._changed.clear()
            if not self.queue:
                await self._changed.wait()
                continue
            if self.mode == "pause":
                if self._steps:
                    self._steps = 0
                    self._release_head()
                    continue
                await self._changed.wait()
                continue
            remaining = self._head_since + self.delay - time.monotonic()
            if remaining <= 0:
                self._release_head()
                continue
            try:
                await asyncio.wait_for(self._changed.wait(), remaining)
            except asyncio.TimeoutError:
                pass

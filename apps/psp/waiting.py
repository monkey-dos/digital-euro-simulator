"""Transactions this bank waits on, keyed by UETR.

Each one has
  - an `on_final(push)` function that books what the final status means for
    this bank (giro debit/credit/release, the bank's copy of the balance);
  - optionally a Future that the I1 handler awaits (INTERPRETATION A7: the
    bank answers the app only after the final settlement status).

The record is registered BEFORE the instruction is sent to the DESP: the DESP
may push the final status before the bank has even read the 201 answer, and
that early push must not be lost. on_final runs even if the app has stopped
waiting (timeout), so the books stay right.
"""
import asyncio

import sim_log


class Pending:
    def __init__(self, me: str):
        self.me = me
        self._items: dict[str, dict] = {}

    def register(self, uetr: str, on_final) -> asyncio.Future:
        """Returns the Future the caller awaits (with wait())."""
        fut = asyncio.get_running_loop().create_future()
        self._items[uetr] = {"on_final": on_final, "future": fut}
        return fut

    def deliver(self, uetr: str, push: dict) -> None:
        """Called after the 204 to a status push has been sent."""
        item = self._items.pop(uetr, None)
        if item is None:
            sim_log.emit("internal", self.me, self.me, "internal", kind="note",
                         note=f"status push for unknown UETR {uetr}: nothing to book")
            return
        try:
            item["on_final"](push)
        finally:
            fut = item["future"]
            if not fut.done():
                fut.set_result(push)

    def cancel(self, uetr: str) -> None:
        """No status push will come (e.g. the DESP rejected in its 201)."""
        self._items.pop(uetr, None)

    @staticmethod
    async def wait(fut: asyncio.Future, timeout: float) -> dict | None:
        """The status push body, or None after the timeout. The record stays, so a late push is still booked."""
        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout)
        except asyncio.TimeoutError:
            return None

    def count(self) -> int:
        return len(self._items)

    def clear(self) -> None:
        self._items.clear()

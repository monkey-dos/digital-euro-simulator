"""Message log: every HTTP message this app sends or receives goes through emit().

THIS IS THE ONE PLACE TO CHANGE when the log should go somewhere else.
Today each event is printed as one readable line and kept in memory
(GET /sim/events). Later emit() can also send the same event to the network
relay / observer ("control room", interface I6) without touching the rest of
the app.

Every event has the same keys (JSON-able):
  time, app, direction, from, to, interface, method, path, status, headers, body
plus seq, kind and, for some events, note / in_reply_to.
  direction  'sent' or 'received' for an HTTP message, 'internal' for a step
             inside the app (ledger booking), which is not an HTTP message.
The shape follows the step files in /examples (from, to, interface, http, body).

Set SIM_LOG_FORMAT=json to print full events as JSON lines instead.
"""
import json
import os
import sys
from collections import deque
from datetime import datetime, timezone

APP_NAME = "app"  # set by app.py at start-up
_events: deque = deque(maxlen=5000)
_seq = 0

REASONS = {200: "OK", 201: "Created", 204: "No Content", 400: "Bad Request", 401: "Unauthorized",
           404: "Not Found", 500: "Internal Server Error"}


def _status_hint(body) -> str:
    """Pick the business status out of a body so the log line says what happened."""
    if not isinstance(body, dict):
        return ""
    for k, v in body.items():
        if k.endswith("TransactionStatus") and isinstance(v, dict):
            reason = (body.get("statusReason") or {}).get("statusReasonCode")
            return f" ({v.get('status')}{', ' + reason if reason else ''})"
    if "reasonCode" in body:
        return f" ({body.get('title')}, {body['reasonCode']})"
    if "ReturnCode" in body:
        return f" (ReturnCode {body['ReturnCode']}{', ' + body['StatusReason'] if body.get('StatusReason') else ''})"
    return ""


def emit(direction: str, frm: str, to: str, interface: str, *, kind="http", method=None, path=None,
         status=None, headers=None, body=None, note=None, in_reply_to=None) -> dict:
    """Record one event and print it. Returns the event."""
    global _seq
    _seq += 1
    now = datetime.now(timezone.utc)
    event = {"seq": _seq, "time": now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z",
             "app": APP_NAME, "direction": direction, "kind": kind,
             "from": frm, "to": to, "interface": interface,
             "method": method, "path": path, "status": status, "headers": headers, "body": body}
    if note is not None:
        event["note"] = note
    if in_reply_to is not None:
        event["in_reply_to"] = in_reply_to
    _events.append(event)
    _print(event)
    return event


def _print(event: dict) -> None:
    if os.environ.get("SIM_LOG_FORMAT") == "json":
        print(json.dumps(event, default=str, ensure_ascii=False), flush=True)
        return
    if event["method"]:
        what = f"{event['method']} {event['path']}"
    elif event["status"] is not None:
        what = f"{event['status']} {REASONS.get(event['status'], '')}{_status_hint(event['body'])}"
    else:
        what = event.get("note", "")
    if event.get("in_reply_to"):
        what += f"  [re {event['in_reply_to']}]"
    print(f"{event['time'][11:23]} [{APP_NAME}] {event['direction']:<8} {event['from']} → {event['to']}: {what}",
          file=sys.stdout, flush=True)


def events_since(seq: int) -> list:
    return [e for e in _events if e["seq"] > seq]

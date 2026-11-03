"""Network relay and control room server of the digital euro simulator
(simulation layer, not part of the ECB scheme).

1. Relay (interface I6 source). Apps call each other through it:
       ANY /r/<from>/<to>/<path>   →   forwarded to <to>'s URL + /<path>
   Every request and every response waits at the gate (gate.py) and is shown
   in the control room. Content is passed on unchanged.
2. Control room. Serves the page (apps/observer) at  /  and its feed:
       GET  /control/history?since=N      events so far (JSON)
       GET  /control/events?since=N       new events, live (server-sent events)
       GET  /control/state                current balances (fetches them now)
3. Game master commands (interface I7, ours):
       POST /control/mode        {"mode": "play" | "pause"}
       POST /control/delay       {"seconds": 1.5}
       POST /control/step        let one waiting message through (pause mode)
       POST /control/reset       all apps back to the test data
       POST /control/holding-limit   {"amount": "100.00"}  (every bank)
       GET  /control/scenarios
       POST /control/scenarios/<example id>
       POST /control/actions     {"action": "pay"|"fund"|"defund", "payer": "anna",
                                  "payee": "ben", "amount": "50.00", "text": "…"}

Run:  python3 relay.py            (port 8100; settings in config/relay.json)
"""
import asyncio
import json
import os
import sys
from decimal import Decimal, InvalidOperation

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(os.path.dirname(HERE))


def _require_dependencies():
    missing = []
    for module in ("starlette", "uvicorn", "httpx"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        sys.exit(f"Relay: missing Python package(s): {', '.join(missing)}.\n"
                 f"Install them with:  pip install -r {os.path.join(HERE, 'requirements.txt')}")


_require_dependencies()

from contextlib import asynccontextmanager  # noqa: E402

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse, Response, StreamingResponse  # noqa: E402
from starlette.routing import Mount, Route  # noqa: E402
from starlette.staticfiles import StaticFiles  # noqa: E402

from feed import Feed  # noqa: E402
from gate import Gate  # noqa: E402
from scenarios import ScenarioError, Scenarios  # noqa: E402

CONFIG_PATH = os.environ.get("RELAY_CONFIG", os.path.join(HERE, "config", "relay.json"))
with open(CONFIG_PATH, encoding="utf-8") as f:
    CFG = json.load(f)
APPS = CFG["apps"]
for slug, url in json.loads(os.environ.get("RELAY_APP_URLS", "{}")).items():  # run_local can move apps
    APPS[slug]["url"] = url
PORT = int(os.environ.get("RELAY_PORT", CFG.get("port", 8100)))
OBSERVER_DIR = os.environ.get("RELAY_OBSERVER_DIR", os.path.join(ROOT, "apps", "observer"))
EXAMPLES_DIR = os.environ.get("RELAY_EXAMPLES_DIR", os.path.join(ROOT, "examples"))
FORWARD_TIMEOUT = float(os.environ.get("RELAY_FORWARD_TIMEOUT", "3600"))  # a paused message may wait long

# Headers that belong to one hop only (RFC 9110 §7.6.1) and are not passed on.
HOP_HEADERS = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer",
               "transfer-encoding", "upgrade", "host", "content-length"}
# httpx hands us the body already decompressed, so the compression header must not be passed back.
RESPONSE_SKIP = HOP_HEADERS | {"content-encoding"}
# Headers shown in the control room (the ones the contracts define, INTERPRETATION T1 and A12).
SHOWN_HEADERS = ["Content-Type", "Request-Id", "Request-Timestamp", "Requesting-Agent", "Response-Timestamp",
                 "Sim-User-DEAN"]

client = httpx.AsyncClient(timeout=FORWARD_TIMEOUT)
feed = Feed(APPS, client)
gate = Gate(mode=os.environ.get("RELAY_MODE", CFG.get("start", {}).get("mode", "play")),
            delay=float(os.environ.get("RELAY_DELAY", CFG.get("start", {}).get("delaySeconds", 1.5))))
scenarios = Scenarios(EXAMPLES_DIR, APPS)
_msg_counter = 0
_running: set[asyncio.Task] = set()
_holding_limit = {"amount": scenarios.test_data.get("holdingLimit", "3000.00")}  # as last set by the game master


def _control_event():
    feed.publish("control", **gate.status())


gate._on_change = _control_event
gate._on_release = lambda msg: (feed.publish("released", id=msg["id"]), feed.refresh_state_soon())


def interface_of(path: str) -> str:
    if path.startswith("/v1/sim/"):
        return "I3 (placeholder)"
    if path.startswith("/v1/"):
        return "I3"
    if path.startswith("/i1/"):
        return "I1"
    return "sim (not ECB)"


def parse_body(raw: bytes):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return raw.decode(errors="replace")


def pass_on_headers(headers, skip=HOP_HEADERS) -> dict:
    return {k: v for k, v in headers.items() if k.lower() not in skip}


def shown_headers(headers: dict) -> dict:
    lower = {k.lower(): v for k, v in headers.items()}
    return {name: lower[name.lower()] for name in SHOWN_HEADERS if name.lower() in lower}


# ---------------------------------------------------------------- the relay itself

async def relay_message(frm: str, to: str, method: str, path: str, headers: dict, raw: bytes,
                        stand_in: bool = False) -> tuple[int, dict, bytes]:
    """Show the request, wait at the gate, forward it, show the answer, wait at the gate, return it."""
    global _msg_counter
    if to not in APPS or "url" not in APPS[to] or frm not in APPS:
        known = ", ".join(APPS)
        return 404, {"content-type": "application/problem+json"}, json.dumps(
            {"title": "Unknown app", "status": 404, "reasonCode": "XFMT",
             "detail": f"Route /r/{frm}/{to}/… is not configured. Known apps: {known}"}).encode()
    iface = interface_of(path)
    _msg_counter += 1
    req_id = f"m{_msg_counter}"
    await feed.poll_internal()  # inside-the-app steps that happened before this message come first
    req = {"id": req_id, "kind": "request", "from": APPS[frm]["name"], "to": APPS[to]["name"],
           "fromId": frm, "toId": to, "interface": iface, "method": method, "path": path,
           "headers": shown_headers(headers), "body": parse_body(raw)}
    if stand_in:
        req["standIn"] = True
    feed.publish("message", **req)
    await gate.wait_turn(req)
    try:
        r = await client.request(method, APPS[to]["url"] + path, content=raw or None, headers=headers)
        status, resp_headers, content = r.status_code, pass_on_headers(r.headers, RESPONSE_SKIP), r.content
    except httpx.HTTPError as e:
        # The target never answered. Tell the caller in the project's problem format
        # (INTERPRETATION T10) with XNET, the code a bank uses for "platform not reachable".
        feed.publish("error", id=req_id, text=f"{APPS[to]['name']} did not answer: {type(e).__name__}")
        body = {"type": "https://digital-euro-simulator.invalid/problems/xnet", "title": "Not reachable (relay)",
                "status": 502, "detail": f"The relay could not reach {APPS[to]['name']}: {type(e).__name__}",
                "instance": path, "reasonCode": "XNET"}
        status, resp_headers, content = 502, {"content-type": "application/problem+json"}, json.dumps(body).encode()
    _msg_counter += 1
    resp_id = f"m{_msg_counter}"  # taken now: other messages may be counted while we wait below
    await feed.poll_internal()
    resp = {"id": resp_id, "kind": "response", "inReplyTo": req_id, "from": APPS[to]["name"],
            "to": APPS[frm]["name"], "fromId": to, "toId": frm, "interface": iface, "method": None,
            "path": path, "status": status, "headers": shown_headers(resp_headers), "body": parse_body(content)}
    if stand_in:
        resp["standIn"] = True
    feed.publish("message", **resp)
    await gate.wait_turn(resp)
    return status, resp_headers, content


async def relay_route(request: Request) -> Response:
    frm, to = request.path_params["frm"], request.path_params["to"]
    # Use the path exactly as it arrived (still percent-encoded), so the relay never changes an address.
    raw = request.scope.get("raw_path", b"").decode("latin-1") or request.url.path
    prefix = f"/r/{frm}/{to}"
    path = raw[len(prefix):] if raw.startswith(prefix) else "/" + request.path_params["rest"]
    path = path or "/"
    if request.url.query:
        path += "?" + request.url.query
    status, headers, content = await relay_message(frm, to, request.method, path,
                                                   pass_on_headers(request.headers), await request.body())
    return Response(content, status_code=status, headers=headers)


# ---------------------------------------------------------------- control room feed

def _since(request: Request) -> int:
    try:
        return max(0, int(request.query_params.get("since", "0")))
    except ValueError:
        return 0


async def history(request: Request):
    since = _since(request)
    return JSONResponse({"events": feed.since(since), "control": gate.status(),
                         "apps": {k: {"name": v["name"], "kind": v["kind"]} for k, v in APPS.items()}})


async def events(request: Request):
    since = _since(request)
    q = feed.subscribe()

    async def stream():
        try:
            for e in feed.since(since):
                yield f"id: {e['seq']}\ndata: {json.dumps(e, default=str, ensure_ascii=False)}\n\n"
            while True:
                try:
                    e = await asyncio.wait_for(q.get(), 15)
                    yield f"id: {e['seq']}\ndata: {json.dumps(e, default=str, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                if await request.is_disconnected():
                    break
        finally:
            feed.unsubscribe(q)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def state(request: Request):
    return JSONResponse(await feed.state_now())


# ---------------------------------------------------------------- game master (I7)

async def _json(request: Request) -> dict:
    try:
        body = json.loads(await request.body() or b"{}")
        return body if isinstance(body, dict) else {}
    except ValueError:
        return {}


def bad(text: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": text}, status_code=status)


async def set_mode(request: Request):
    try:
        gate.set_mode((await _json(request)).get("mode"))
    except ValueError as e:
        return bad(str(e))
    return JSONResponse({"ok": True, **gate.status()})


async def set_delay(request: Request):
    try:
        gate.set_delay((await _json(request)).get("seconds"))
    except (ValueError, TypeError):
        return bad("seconds must be a number between 0 and 60")
    return JSONResponse({"ok": True, **gate.status()})


async def step(request: Request):
    if gate.mode != "pause":
        return bad("Step works in pause mode", 409)
    if not gate.step():
        return JSONResponse({"ok": False, "error": "Nothing is waiting", **gate.status()})
    return JSONResponse({"ok": True, **gate.status()})


async def reset(request: Request):
    if _running:
        return bad("A scenario is still running. Let it finish (press Play), then reset.", 409)
    if gate.queue:
        # Releasing them now would let old messages reach freshly reset apps and the books would disagree.
        return bad("Messages are still on their way. Let them arrive (press Play), then reset.", 409)
    results = {}
    for slug, a in APPS.items():
        if a.get("url"):
            try:
                r = await client.post(a["url"] + "/sim/reset", timeout=5)
                results[a["name"]] = r.status_code == 200
            except httpx.HTTPError:
                results[a["name"]] = False
    await feed.skip_old_app_events()
    feed.clear()
    feed.publish("reset", results=results)
    _control_event()
    await feed.state_now()
    return JSONResponse({"ok": all(results.values()), "apps": results})


def _limit(value) -> str | None:
    """A holding limit as the banks accept it: a finite amount 0–1,000,000 with at most two decimals."""
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not d.is_finite() or d < 0 or d > Decimal("1000000") or d != d.quantize(Decimal("0.01")):
        return None
    return f"{d:.2f}"


async def _set_holding_limit(amount: str) -> dict:
    out = {}
    body = {"command": "SET_HOLDING_LIMIT", "amount": {"currency": "EUR", "amount": amount}}
    for slug, a in APPS.items():
        if a["kind"] == "bank":
            try:
                r = await client.post(a["url"] + "/sim/holding-limit", json=body, timeout=5)
                out[a["name"]] = r.status_code == 200
            except httpx.HTTPError:
                out[a["name"]] = False
    if all(out.values()):
        feed.publish("control", **gate.status(), gameMaster=f"Holding limit set to {amount} EUR at every bank",
                     holdingLimit=amount)
    else:
        refused = ", ".join(k for k, v in out.items() if not v)
        feed.publish("error", text=f"Holding limit {amount} EUR not accepted by: {refused}")
    feed.refresh_state_soon()
    return out


async def holding_limit(request: Request):
    if _running:
        return bad("A scenario is still running. Change the holding limit when it has finished.", 409)
    amount = _limit((await _json(request)).get("amount"))
    if amount is None:
        return bad('Expected {"amount": "100.00"}: 0 to 1,000,000 EUR, at most two decimals')
    banks = await _set_holding_limit(amount)
    if all(banks.values()):
        _holding_limit["amount"] = amount
    return JSONResponse({"ok": all(banks.values()), "banks": banks,
                         **({} if all(banks.values()) else {"error": "Not every bank accepted the new limit"})})


async def list_scenarios(request: Request):
    return JSONResponse(scenarios.list())


async def _run(call: dict):
    """Play the banking app: send the first message and wait for the bank's answer."""
    feed.publish("scenario", status="started", id=call["id"], title=call["title"], steps=call["steps"],
                 standIn=True)
    restore = None
    try:
        for gm in call["gameMaster"]:
            if gm["body"].get("command") == "SET_HOLDING_LIMIT":
                restore = _holding_limit["amount"]  # the limit the game master had set before
                await _set_holding_limit(gm["body"]["amount"]["amount"])
        status, _, content = await relay_message(call["from"], call["to"], "POST", call["path"], call["headers"],
                                                 json.dumps(call["body"], ensure_ascii=False).encode(), stand_in=True)
        answer = parse_body(content)
        ok = status == 200 and isinstance(answer, dict) and answer.get("ReturnCode") == 0
        await asyncio.sleep(0.6)  # let the last inside-the-app steps (e.g. giro credit) arrive first
        await feed.poll_internal()
        feed.publish("scenario", status="finished", id=call["id"], title=call["title"], ok=ok,
                     httpStatus=status, answer=answer)
    except Exception as e:  # never leave the control room waiting without an answer
        feed.publish("scenario", status="failed", id=call["id"], title=call["title"], ok=False, error=repr(e))
    finally:
        if restore:
            await _set_holding_limit(restore)
        feed.refresh_state_soon()


def _start(call: dict) -> JSONResponse:
    if _running:
        return bad("A scenario is still running. Let it finish first.", 409)
    task = asyncio.create_task(_run(call))
    _running.add(task)
    task.add_done_callback(_running.discard)
    return JSONResponse({"ok": True, "started": call["title"]}, status_code=202)


async def run_example(request: Request):
    try:
        return _start(scenarios.example_call(request.path_params["id"]))
    except ScenarioError as e:
        return bad(str(e), 404)


async def run_action(request: Request):
    b = await _json(request)
    try:
        return _start(scenarios.action_call(b.get("action"), b.get("payer"), b.get("amount"), b.get("payee"),
                                            b.get("text")))
    except ScenarioError as e:
        return bad(str(e))


async def health(request: Request):
    return JSONResponse({"status": "ok", "app": "Network relay"})


# ---------------------------------------------------------------- app

@asynccontextmanager
async def lifespan(app):
    gate.start()
    await feed.skip_old_app_events()
    poller = asyncio.create_task(feed.background_poll())
    _control_event()
    asyncio.create_task(feed.state_now())
    yield
    poller.cancel()
    await gate.stop()
    await client.aclose()


class Cors:
    """Lets the control room page opened from a file or another address read the feed (local use only)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/control"):
            return await self.app(scope, receive, send)
        if scope["method"] == "OPTIONS":
            await send({"type": "http.response.start", "status": 204, "headers": [
                (b"access-control-allow-origin", b"*"), (b"access-control-allow-methods", b"GET, POST, OPTIONS"),
                (b"access-control-allow-headers", b"content-type")]})
            return await send({"type": "http.response.body", "body": b""})

        async def send_with_cors(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [(b"access-control-allow-origin", b"*")]
            await send(message)
        return await self.app(scope, receive, send_with_cors)


routes = [
    Route("/r/{frm}/{to}/{rest:path}", relay_route, methods=["GET", "POST", "PUT", "PATCH", "DELETE"]),
    Route("/health", health, methods=["GET"]),
    Route("/control/history", history, methods=["GET"]),
    Route("/control/events", events, methods=["GET"]),
    Route("/control/state", state, methods=["GET"]),
    Route("/control/mode", set_mode, methods=["POST"]),
    Route("/control/delay", set_delay, methods=["POST"]),
    Route("/control/step", step, methods=["POST"]),
    Route("/control/reset", reset, methods=["POST"]),
    Route("/control/holding-limit", holding_limit, methods=["POST"]),
    Route("/control/scenarios", list_scenarios, methods=["GET"]),
    Route("/control/scenarios/{id}", run_example, methods=["POST"]),
    Route("/control/actions", run_action, methods=["POST"]),
]
if os.path.isdir(OBSERVER_DIR):
    routes.append(Mount("/", StaticFiles(directory=OBSERVER_DIR, html=True), name="control-room"))

app = Cors(Starlette(routes=routes, lifespan=lifespan))

if __name__ == "__main__":
    print(f"Network relay on http://127.0.0.1:{PORT}  ·  control room: http://127.0.0.1:{PORT}/", flush=True)
    for slug, a in APPS.items():
        if a.get("url"):
            print(f"  /r/<from>/{slug}/…  →  {a['url']}  ({a['name']})", flush=True)
    uvicorn.run(app, host=os.environ.get("SIM_HOST", "127.0.0.1"), port=PORT, log_level="warning")

"""HTTP plumbing for this app: JSON in/out, technical headers (INTERPRETATION T1),
problem+json errors (T10) and logging of every HTTP message via sim_log.emit()."""
import json
from decimal import Decimal

import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

import sim_log
from reasons import XFMT, XHDR
from sim_ids import BIC_RE, DATETIME_RE, UUID_RE, now_ts, uuid4

PROBLEM_SCHEMA = "common/problem.schema.json"
# Header names we log (HTTP header names are case-insensitive; we print them as in /examples).
KNOWN_HEADERS = ["Content-Type", "Request-Id", "Request-Timestamp", "Requesting-Agent",
                 "Response-Timestamp", "Sim-User-DEAN"]
# Not logged: health checks and reading the log itself (they would only add noise).
NOT_LOGGED = {("GET", "/health"), ("GET", "/sim/events")}


def _default(o):
    if isinstance(o, Decimal):
        return float(o)  # only I1 amounts are numbers; I3 amounts are strings (C6)
    raise TypeError(f"not JSON serialisable: {type(o)}")


def dumps(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=_default).encode()


def loads(raw: bytes):
    """parse_float=Decimal keeps amounts exact (19.99 stays 19.99)."""
    return json.loads(raw, parse_float=Decimal)


class Json(JSONResponse):
    def render(self, content) -> bytes:
        return dumps(content)


def pick_headers(headers) -> dict:
    lower = {k.lower(): v for k, v in headers.items()}
    return {name: lower[name.lower()] for name in KNOWN_HEADERS if name.lower() in lower}


def response_headers(request_id: str | None, json_body=True) -> dict:
    """T1: responses carry Request-Id (echo of the request) and Response-Timestamp."""
    h = {"Content-Type": "application/json"} if json_body else {}
    if request_id:
        h["Request-Id"] = request_id
    h["Response-Timestamp"] = now_ts()
    return h


def request_headers(requesting_agent: str | None = None) -> dict:
    """T1: Request-Id (UUID), Request-Timestamp; Requesting-Agent only bank → DESP."""
    h = {"Content-Type": "application/json", "Request-Id": uuid4(), "Request-Timestamp": now_ts()}
    if requesting_agent:
        h["Requesting-Agent"] = requesting_agent
    return h


def problem(schemas, request: Request, status: int, reason: str, title: str, detail: str,
            errors: list | None = None) -> Json:
    """Technical error as application/problem+json (D2-1; key names: INTERPRETATION T10)."""
    body = {"type": f"https://digital-euro-simulator.invalid/problems/{reason.lower()}",
            "title": title[:140], "status": status, "detail": detail[:500],
            "instance": request.url.path, "reasonCode": reason}
    if errors:
        body["additionalErrors"] = [{"location": e["location"], "detail": e["detail"][:300]} for e in errors[:20]]
    schemas.check_outgoing(PROBLEM_SCHEMA, body)
    headers = response_headers(request.headers.get("request-id"))
    headers["Content-Type"] = "application/problem+json"
    return Json(body, status_code=status, headers=headers, media_type="application/problem+json")


async def read_valid_body(schemas, request: Request, schema: str):
    """Parse the JSON body and validate it against a contract schema.
    Returns (body, None) or (None, problem response)."""
    try:
        body = loads(await request.body())
    except ValueError as e:
        return None, problem(schemas, request, 400, XFMT, "Body is not valid JSON", str(e))
    errors = schemas.errors(schema, body)
    if errors:
        return None, problem(schemas, request, 400, XFMT, "Body does not match the contract",
                             f"Checked against contracts/{schema}", errors)
    return body, None


def check_request_headers(schemas, request: Request, need_agent: bool):
    """T1: Request-Id (UUID) and Request-Timestamp (date-time, C10); for bank → DESP
    calls also Requesting-Agent (BIC). Returns (headers, None) or (None, problem)."""
    h = pick_headers(request.headers)
    bad = []
    if not UUID_RE.match(h.get("Request-Id", "")):
        bad.append({"location": "header Request-Id", "detail": "missing or not a UUID"})
    if not DATETIME_RE.match(h.get("Request-Timestamp", "")):
        bad.append({"location": "header Request-Timestamp", "detail": "missing, or not UTC / explicit offset (C10)"})
    if need_agent and not BIC_RE.match(h.get("Requesting-Agent", "")):
        bad.append({"location": "header Requesting-Agent", "detail": "missing or not a BIC"})
    if bad:
        return None, problem(schemas, request, 400, XHDR, "Technical header invalid", "See INTERPRETATION T1", bad)
    return h, None


def interface_of(path: str) -> str:
    if path.startswith("/v1/sim/"):
        return "I3 (placeholder)"
    if path.startswith("/v1/"):
        return "I3"
    if path.startswith("/i1/"):
        return "I1"
    return "sim (not ECB)"


def _parse(raw: bytes):
    if not raw:
        return None
    try:
        return loads(raw)
    except ValueError:
        return raw.decode(errors="replace")


def logged(me: str, caller):
    """Wrap an endpoint so the request it receives and the response it sends are
    each logged as one event. `caller(request)` names who called us."""
    def deco(endpoint):
        async def wrapper(request: Request) -> Response:
            skip = (request.method, request.url.path) in NOT_LOGGED
            frm, iface = caller(request), interface_of(request.url.path)
            what = f"{request.method} {request.url.path}"
            if not skip:
                body = _parse(await request.body())  # Starlette caches the body; the endpoint can read it again
                sim_log.emit("received", frm, me, iface, method=request.method, path=request.url.path,
                             headers=pick_headers(request.headers), body=body)
            try:
                response = await endpoint(request)
            except Exception as e:  # never hide a crash: log it, Starlette answers 500
                sim_log.emit("internal", me, me, "internal", kind="note", note=f"ERROR while handling {what}: {e!r}")
                raise
            if not skip:
                sim_log.emit("sent", me, frm, iface, status=response.status_code, in_reply_to=what,
                             headers=pick_headers(response.headers), body=_parse(response.body))
            return response
        return wrapper
    return deco


async def call(client: httpx.AsyncClient, me: str, to: str, method: str, url: str, path: str, body, headers: dict):
    """Make an outgoing call and log the request and the response.
    Returns (status, headers, parsed body). Network errors propagate (httpx.HTTPError)."""
    iface = interface_of(path)
    sim_log.emit("sent", me, to, iface, method=method, path=path, headers=pick_headers(headers), body=body)
    try:
        r = await client.request(method, url + path, content=dumps(body) if body is not None else None, headers=headers)
    except httpx.HTTPError as e:
        sim_log.emit("internal", me, me, "internal", kind="note", note=f"no answer from {to} for {method} {path}: {e!r}")
        raise
    parsed = _parse(r.content)
    sim_log.emit("received", to, me, iface, status=r.status_code, in_reply_to=f"{method} {path}",
                 headers=pick_headers(r.headers), body=parsed)
    return r.status_code, pick_headers(r.headers), parsed

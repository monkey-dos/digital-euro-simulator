"""PSP – bank back-end of the digital euro simulator (reference implementation).

One template, started once per bank with its own configuration (ADR 0006):
    python3 app.py config/psp-a.json      # PSP A, port 8001
    python3 app.py config/psp-b.json      # PSP B, port 8002

Offers
  I1  POST /i1/messages            for its banking app (Annex D1-1): payment
                                   initiation, online funding / defunding request
  I3  PSP API (Annex D2-7), called by the DESP:
      POST /v1/payment-instructions                 forwarded payment (payee side)
      POST /v1/payment-instructions/{id}/status     final status push → 204
      POST /v1/fundings/{id}/status                 final status push → 204
      POST /v1/defundings/{id}/status               final status push → 204
  Simulation only (not ECB): GET /health, GET /sim/state, GET /sim/events,
      POST /sim/holding-limit, POST /sim/reset,
      POST /sim/helicopter-money (game master money creation, ADR 0009)
Calls the DESP API (alias lookup placeholder, payment instructions, fundings, defundings).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _require_dependencies():
    """Fail with a clear message instead of an obscure ImportError."""
    missing = []
    for module, package in (("starlette", "starlette"), ("uvicorn", "uvicorn"), ("httpx", "httpx"),
                            ("jsonschema", "jsonschema"), ("referencing", "referencing")):
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    if missing:
        sys.exit(f"PSP: missing Python package(s): {', '.join(missing)}.\n"
                 f"Install them with:  pip install -r {os.path.join(HERE, 'requirements.txt')}")


def _load_config() -> dict:
    path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PSP_CONFIG")
    if not path:
        sys.exit("Usage: python3 app.py config/psp-a.json   (or set PSP_CONFIG)")
    if not os.path.isabs(path) and not os.path.exists(path):
        path = os.path.join(HERE, path)
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["despUrl"] = os.environ.get("DESP_URL", cfg["despUrl"])
    cfg["port"] = int(os.environ.get("PSP_PORT", cfg["port"]))
    return cfg


_require_dependencies()
CFG = _load_config()

from contextlib import asynccontextmanager  # noqa: E402
from decimal import Decimal, InvalidOperation  # noqa: E402

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.background import BackgroundTask  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import Response  # noqa: E402
from starlette.routing import Route  # noqa: E402

import sim_log  # noqa: E402
from customers import Bank  # noqa: E402
from desp_client import DespClient  # noqa: E402
from helicopter import HelicopterLedger  # noqa: E402
from http_util import (Json, check_request_headers, logged, problem, read_valid_body,  # noqa: E402
                       response_headers)
from payee import PayeeSide  # noqa: E402
from payer import PayerSide  # noqa: E402
from reasons import XAUT, XFMT, XINT, Rejection  # noqa: E402
from schema_check import SchemaCheck  # noqa: E402
from sim_ids import fmt, money, now_ts  # noqa: E402
from waiting import Pending  # noqa: E402

ME = CFG["name"]
sim_log.APP_NAME = ME
S3 = "i3-psp-desp/schemas/psp-api/"
S1 = "i1-app-psp/schemas/"
SEED = os.environ.get("SIM_SEED") or os.path.join(HERE, "..", "..", "examples", "test-data.json")

schemas = SchemaCheck()
bank = Bank(ME)
helicopter = HelicopterLedger(ME)
pending = Pending(ME)
desp = DespClient(ME, CFG["bic"], CFG["despUrl"], schemas)
payer_side = PayerSide(CFG, bank, desp, pending, float(os.environ.get("PSP_STATUS_TIMEOUT", "15")))
payee_side = PayeeSide(CFG, bank, pending, schemas, payer_side)
_counter = {"resp": 0}


def seed():
    with open(SEED, encoding="utf-8") as f:
        data = json.load(f)
    bank.seed(data["users"], CFG["seedBank"])
    payer_side.holding_limit = money(CFG["holdingLimit"])
    pending.clear()
    helicopter.clear()


def caller(request: Request) -> str:
    p = request.url.path
    if p.startswith("/i1/"):
        return CFG["appName"]
    if p.startswith("/v1/"):
        return "DESP"
    if p.startswith("/sim/"):
        return "Game Master"  # simulation commands (I7, ours)
    return "client"


me = logged(ME, caller)

# ---------------------------------------------------------------- I1: banking app → bank

I1_SCHEMAS = {
    "Individual user payment initiation": "payment-initiation.request.schema.json",
    "Online funding request": "funding-defunding-request.request.schema.json",
    "Online defunding request": "funding-defunding-request.request.schema.json",
}


def _i1_answer(msg: dict, code: str | None) -> Json:
    """Outgoing envelope (D1-1): ReturnCode 0 = successful, 1 = failure + StatusReason (A8, A13)."""
    _counter["resp"] += 1
    body = {"MessageIdentification": f"{CFG['messagePrefix']}-RESP-{_counter['resp']:04d}"}
    if msg.get("MessageIdentification"):
        body["OriginalMessageIdentification"] = msg["MessageIdentification"]
    body["CreationDateTime"] = now_ts()
    body["ReturnCode"] = 0 if code is None else 1
    if code:
        body["StatusReason"] = code
    schemas.check_outgoing(S1 + "response.schema.json", body)
    return Json(body, status_code=200)


@me
async def i1_messages(request: Request):
    """POST /i1/messages (INTERPRETATION A1). Answers after the final settlement status (A7)."""
    # A12 (placeholder): the logged-in user, instead of a real session after SCA
    user = bank.by_dean.get(request.headers.get("sim-user-dean", ""))
    if user is None:
        return problem(schemas, request, 401, XAUT, "No logged-in user",
                       "Send the header Sim-User-DEAN with the DEAN of a customer of this bank (INTERPRETATION A12).")
    try:
        parsed = json.loads(await request.body())
    except ValueError as e:
        return problem(schemas, request, 400, XFMT, "Body is not valid JSON", str(e))
    event = parsed.get("EventIdentification") if isinstance(parsed, dict) else None
    if event not in I1_SCHEMAS:
        return problem(schemas, request, 400, XFMT, "Unknown or missing EventIdentification",
                       "Supported: " + ", ".join(I1_SCHEMAS))
    msg, err = await read_valid_body(schemas, request, S1 + I1_SCHEMAS[event])
    if err:
        return err
    try:
        if event == "Individual user payment initiation":
            await payer_side.payment(user, msg)
        else:
            await payer_side.funding(user, msg)
        code = None
    except Rejection as r:
        sim_log.emit("internal", ME, ME, "internal", kind="note", note=f"rejected for {user.name}: {r}")
        code = r.code
    except Exception as e:  # a bug: still give the app a proper answer
        sim_log.emit("internal", ME, ME, "internal", kind="note", note=f"ERROR: {e!r}")
        code = XINT
    return _i1_answer(msg, code)


# ---------------------------------------------------------------- I3: PSP API, called by the DESP

@me
async def forwarded_payment_instruction(request: Request):
    """PSP API POST /v1/payment-instructions (D2-7 p.102–106): we are the payee bank."""
    headers, err = check_request_headers(schemas, request, need_agent=False)
    if err:
        return err
    body, err = await read_valid_body(schemas, request, S3 + "post-payment-instructions.request.schema.json")
    if err:
        return err
    resp = payee_side.answer_forwarded(body)
    schemas.check_outgoing(S3 + "post-payment-instructions.response-201.schema.json", resp)
    return Json(resp, status_code=201, headers=response_headers(headers["Request-Id"]))


def _status_endpoint(schema: str):
    @me
    async def endpoint(request: Request):
        """Final status push (D2-7 p.95–109): answer 204 without body, then book (A11)."""
        headers, err = check_request_headers(schemas, request, need_agent=False)
        if err:
            return err
        body, err = await read_valid_body(schemas, request, S3 + schema)
        if err:
            return err
        uetr = body["paymentIdentification"]["UETR"]
        return Response(status_code=204, headers=response_headers(headers["Request-Id"], json_body=False),
                        background=BackgroundTask(pending.deliver, uetr, body))
    return endpoint


# ---------------------------------------------------------------- simulation only (not ECB)

async def health(request: Request):
    return Json({"app": ME, "bic": CFG["bic"], "ok": True})


async def sim_state(request: Request):
    return Json({"app": ME, "bic": CFG["bic"], "holdingLimit": fmt(payer_side.holding_limit),
                 "customers": [c.view() for c in bank.by_dean.values()], "pendingTransactions": pending.count(),
                 "helicopterMoney": helicopter.state()})


async def sim_events(request: Request):
    return Json({"events": sim_log.events_since(int(request.query_params.get("since", "0")))})


@me
async def sim_holding_limit(request: Request):
    """Game master command SET_HOLDING_LIMIT (I7, ours; ADR 0005). Body as in
    examples/p2p-waterfall-two-psps/00-game-master-holding-limit.json."""
    try:
        body = json.loads(await request.body())
        amount = body["amount"]
        if body.get("command") != "SET_HOLDING_LIMIT" or amount["currency"] != "EUR":
            raise ValueError
        limit = money(amount["amount"])
        if limit < 0:
            raise ValueError
    except (ValueError, KeyError, TypeError, InvalidOperation):
        return problem(schemas, request, 400, XFMT, "Invalid command",
                       'Expected {"command": "SET_HOLDING_LIMIT", "amount": {"currency": "EUR", "amount": "100.00"}}')
    payer_side.holding_limit = limit
    return Json({"holdingLimit": fmt(limit)})


async def sim_helicopter_money(request: Request):
    """Helicopter Money (ADR 0009, simulation only), called by the game master after the DESP booked it.
    {"account": "digital-euro"|"giro", "dean": "...", "amount": "100.00", "helicopterId": "..."}
    {"reverse": "<helicopterId>"}   undo one booking"""
    def refuse(status: int, text: str):
        return Json({"ok": False, "error": text}, status_code=status)
    try:
        body = json.loads(await request.body() or b"{}")
        if not isinstance(body, dict):
            raise ValueError
    except ValueError:
        return refuse(400, "Body is not a JSON object")
    if body.get("reverse"):
        try:
            helicopter.reverse(bank, str(body["reverse"]))
        except Rejection as r:
            return refuse(404, str(r))
        except ValueError as e:
            return refuse(409, str(e))
        return Json({"ok": True})
    hid = body.get("helicopterId")
    if not isinstance(hid, str) or not hid:
        return refuse(400, "helicopterId is missing")
    if any(b["helicopterId"] == hid for b in helicopter.bookings):
        return refuse(409, f"Helicopter Money booking {hid} exists already")
    try:
        amount = money(body.get("amount"))
        if amount <= 0 or amount > Decimal("1000000") or Decimal(str(body["amount"])) != amount:
            raise ValueError
    except (InvalidOperation, ValueError, KeyError, TypeError):
        return refuse(400, "Amount must be positive, at most 1,000,000.00, with at most two decimals")
    account = body.get("account")
    if account not in ("digital-euro", "giro"):
        return refuse(400, 'account must be "digital-euro" or "giro"')
    c = bank.by_dean.get(str(body.get("dean")))
    if c is None:
        return refuse(404, "No customer with this DEAN at this bank")
    if account == "digital-euro":
        if c.projected() + amount > payer_side.holding_limit:
            return refuse(409, f"{c.name} would hold more than the holding limit of {fmt(payer_side.holding_limit)} EUR "
                               f"({fmt(c.projected())} EUR now incl. incoming, {fmt(amount)} EUR new)")
        helicopter.book_digital_euro(c, amount, hid)
    else:
        helicopter.book_giro(bank, c, amount, hid)
    return Json({"ok": True, "helicopterId": hid, "digitalEuro": fmt(c.balance), "giro": fmt(c.giro)})


async def sim_reset(request: Request):
    seed()
    sim_log.emit("internal", ME, ME, "sim (not ECB)", kind="note", note="state reset to seed data")
    return Json({"ok": True})


@asynccontextmanager
async def lifespan(app):
    desp.client = httpx.AsyncClient(timeout=float(os.environ.get("PSP_HTTP_TIMEOUT", "10")))
    yield
    await desp.client.aclose()


routes = [
    Route("/i1/messages", i1_messages, methods=["POST"]),
    Route("/v1/payment-instructions", forwarded_payment_instruction, methods=["POST"]),
    Route("/v1/payment-instructions/{id}/status", _status_endpoint("post-payment-instruction-status.request.schema.json"), methods=["POST"]),
    Route("/v1/fundings/{id}/status", _status_endpoint("post-funding-status.request.schema.json"), methods=["POST"]),
    Route("/v1/defundings/{id}/status", _status_endpoint("post-defunding-status.request.schema.json"), methods=["POST"]),
    Route("/health", health, methods=["GET"]),
    Route("/sim/state", sim_state, methods=["GET"]),
    Route("/sim/events", sim_events, methods=["GET"]),
    Route("/sim/holding-limit", sim_holding_limit, methods=["POST"]),
    Route("/sim/reset", sim_reset, methods=["POST"]),
    Route("/sim/helicopter-money", sim_helicopter_money, methods=["POST"]),
]
seed()
app = Starlette(routes=routes, lifespan=lifespan)

if __name__ == "__main__":
    print(f"{ME} ({CFG['bic']}) listening on http://127.0.0.1:{CFG['port']}, DESP at {CFG['despUrl']}", flush=True)
    uvicorn.run(app, host=os.environ.get("SIM_HOST", "127.0.0.1"), port=CFG["port"], log_level="warning")

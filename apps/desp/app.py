"""DESP – central platform of the digital euro simulator (reference implementation).

Offers (interface I3, DESP API, Annex D2-7):
  POST /v1/payment-instructions     payer bank → DESP (with funding/defunding parts)
  POST /v1/fundings                 bank → DESP (standalone funding)
  POST /v1/defundings               bank → DESP (standalone defunding)
  POST /v1/sim/alias-lookup         PLACEHOLDER alias lookup (INTERPRETATION T5)
Calls (PSP API of every bank): forwarded POST /v1/payment-instructions and the
status pushes …/{id}/status.
Simulation only (not ECB): GET /health, GET /sim/state, GET /sim/events, POST /sim/reset,
  POST /sim/helicopter-money (game master money creation, ADR 0002).

Run:  python3 app.py            (port 8000; set DESP_PORT to change)
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
        sys.exit(f"DESP: missing Python package(s): {', '.join(missing)}.\n"
                 f"Install them with:  pip install -r {os.path.join(HERE, 'requirements.txt')}")


_require_dependencies()

from contextlib import asynccontextmanager  # noqa: E402
from decimal import Decimal, InvalidOperation  # noqa: E402

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.routing import Route  # noqa: E402

import sim_log  # noqa: E402
from access import AccessManagement, Participants, load_seed  # noqa: E402
from http_util import (Json, check_request_headers, logged, problem, read_valid_body,  # noqa: E402
                       response_headers)
from ledger import Ledger  # noqa: E402
from reasons import XALI  # noqa: E402
from schema_check import SchemaCheck  # noqa: E402
from settlement import Engine  # noqa: E402
from sim_ids import money, now_ts  # noqa: E402

sim_log.APP_NAME = "DESP"
S = "i3-psp-desp/schemas/"

schemas = SchemaCheck()
participants = Participants()
access = AccessManagement()
ledger = Ledger()
engine = Engine(ledger, participants, schemas)


def seed():
    """Load test users, ledger entries and DCAs from examples/test-data.json (or SIM_SEED)."""
    data = load_seed()
    banks = data["banks"]
    access.seed(data["users"], banks)
    ledger.seed({u["entry"]: (banks[u["bank"]]["bic"], u["balance"]) for u in data["users"].values()},
                {banks[k]["bic"]: v for k, v in data["dcaBalances"].items()})
    engine.reset()


def caller(request: Request) -> str:
    """Name of the calling app for the log: the bank in Requesting-Agent (T1), else 'client'."""
    agent = request.headers.get("requesting-agent")
    return participants.name(agent) if agent else "client"


me = logged("DESP", caller)


async def _i3_request(request: Request, schema: str):
    """Common checks for every bank → DESP call: technical header (T1) and body schema."""
    headers, err = check_request_headers(schemas, request, need_agent=True)
    if err:
        return None, None, err
    body, err = await read_valid_body(schemas, request, S + schema)
    if err:
        return None, None, err
    return headers, body, None


def _created(headers: dict, body: dict, schema: str) -> Json:
    schemas.check_outgoing(S + schema, body)
    return Json(body, status_code=201, headers=response_headers(headers["Request-Id"]))


@me
async def post_payment_instructions(request: Request):
    """DESP API POST /v1/payment-instructions (D2-7 p.57–64)."""
    headers, body, err = await _i3_request(request, "desp-api/post-payment-instructions.request.schema.json")
    if err:
        return err
    resp = engine.accept_payment_instruction(headers["Requesting-Agent"], body)
    return _created(headers, resp, "desp-api/post-payment-instructions.response-201.schema.json")


def _funding_endpoint(kind: str):
    @me
    async def endpoint(request: Request):
        """DESP API POST /v1/fundings (D2-7 p.49–53) or /v1/defundings (p.53–57)."""
        headers, body, err = await _i3_request(request, f"desp-api/post-{kind}s.request.schema.json")
        if err:
            return err
        resp = engine.accept_funding(kind, headers["Requesting-Agent"], body)
        return _created(headers, resp, f"desp-api/post-{kind}s.response-201.schema.json")
    return endpoint


@me
async def alias_lookup(request: Request):
    """PLACEHOLDER POST /v1/sim/alias-lookup (INTERPRETATION T5)."""
    headers, body, err = await _i3_request(request, "placeholder/alias-lookup.request.schema.json")
    if err:
        return err
    found = access.lookup_alias(body["proxyAlias"], body["proxyAliasType"])
    if not found:
        return problem(schemas, request, 404, XALI, "Alias not registered",
                       f"No digital euro account is registered for this {body['proxyAliasType']} alias.")
    resp = {"DEAN": found[0], "digitalEuroPspId": found[1]}
    schemas.check_outgoing(S + "placeholder/alias-lookup.response-200.schema.json", resp)
    return Json(resp, status_code=200, headers=response_headers(headers["Request-Id"]))


# ---------------------------------------------------------------- simulation only (not ECB)

async def health(request: Request):
    return Json({"app": "DESP", "ok": True})


async def sim_state(request: Request):
    """Everything the observer needs: ledger, DCAs, money check, access data, recent transactions."""
    return Json({"app": "DESP", **ledger.state(), "accessManagement": access.state(),
                 "transactions": list(engine.transactions)})


async def sim_events(request: Request):
    since = int(request.query_params.get("since", "0"))
    return Json({"events": sim_log.events_since(since)})


async def sim_reset(request: Request):
    """Back to the seed data (for repeatable test runs)."""
    seed()
    sim_log.emit("internal", "DESP", "DESP", "sim (not ECB)", kind="note", note="state reset to seed data")
    return Json({"ok": True})


async def sim_helicopter_money(request: Request):
    """Helicopter Money (ADR 0002, simulation only): new money, impossible with the real digital euro.
    {"target": "entry", "entryId": "...", "amount": "100.00", "helicopterId": "..."}  digital euro on a ledger entry
    {"target": "dca", "bic": "...", "amount": "100.00", "helicopterId": "..."}        central bank money on a DCA
    {"reverse": "<helicopterId>"}                                                    undo one booking"""
    def refuse(status: int, text: str):
        return Json({"ok": False, "error": text}, status_code=status)
    try:
        body = json.loads(await request.body() or b"{}")
        if not isinstance(body, dict):
            raise ValueError
    except ValueError:
        return refuse(400, "Body is not a JSON object")
    hid = body.get("reverse") or body.get("helicopterId")
    if not isinstance(hid, str) or not hid:
        return refuse(400, "helicopterId is missing")
    try:
        if body.get("reverse"):
            bookings = ledger.helicopter_reverse(hid)
            note = "Helicopter Money undone"
        else:
            try:
                amount = money(body.get("amount"))
                if amount <= 0 or amount > Decimal("1000000") or Decimal(str(body["amount"])) != amount:
                    raise ValueError
            except (InvalidOperation, ValueError, KeyError, TypeError):
                return refuse(400, "Amount must be positive, at most 1,000,000.00, with at most two decimals")
            if body.get("target") == "entry":
                bookings = ledger.helicopter_entry(hid, str(body.get("entryId")), amount)
            elif body.get("target") == "dca":
                bookings = ledger.helicopter_dca(hid, str(body.get("bic")), amount)
            else:
                return refuse(400, 'target must be "entry" or "dca"')
            note = "Helicopter Money created"
    except KeyError as e:
        return refuse(404, str(e.args[0]))
    except ValueError as e:
        return refuse(409, str(e))
    for b in bookings:
        if b["entry"].startswith("DCA of "):
            b["entry"] = "DCA of " + participants.name(b["entry"][len("DCA of "):])
    sim_log.emit("internal", "DESP", "DESP ledger", "internal", kind="ledger",
                 body={"helicopterMoney": True, "helicopterId": hid, "reversed": bool(body.get("reverse")),
                       "settlementDateTime": now_ts(), "bookings": bookings},
                 note=f"{note}: " + ", ".join(f"{b['entry']} {b['change']}" for b in bookings))
    return Json({"ok": True, "helicopterId": hid, "bookings": bookings})


@asynccontextmanager
async def lifespan(app):
    engine.client = httpx.AsyncClient(timeout=float(os.environ.get("DESP_FORWARD_TIMEOUT", "10")))
    yield
    await engine.client.aclose()


routes = [
    Route("/v1/payment-instructions", post_payment_instructions, methods=["POST"]),
    Route("/v1/fundings", _funding_endpoint("funding"), methods=["POST"]),
    Route("/v1/defundings", _funding_endpoint("defunding"), methods=["POST"]),
    Route("/v1/sim/alias-lookup", alias_lookup, methods=["POST"]),
    Route("/health", health, methods=["GET"]),
    Route("/sim/state", sim_state, methods=["GET"]),
    Route("/sim/events", sim_events, methods=["GET"]),
    Route("/sim/reset", sim_reset, methods=["POST"]),
    Route("/sim/helicopter-money", sim_helicopter_money, methods=["POST"]),
]
seed()
app = Starlette(routes=routes, lifespan=lifespan)

if __name__ == "__main__":
    port = int(os.environ.get("DESP_PORT", "8000"))
    print(f"DESP listening on http://127.0.0.1:{port}  (participants: {', '.join(participants.banks)})", flush=True)
    uvicorn.run(app, host=os.environ.get("SIM_HOST", "127.0.0.1"), port=port, log_level="warning")

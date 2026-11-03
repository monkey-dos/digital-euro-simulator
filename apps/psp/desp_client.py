"""Calls from this bank to the DESP API (interface I3, Annex D2-7).

Every outgoing body is checked against its contract schema before sending,
every answer after receiving. Headers per INTERPRETATION T1, including
Requesting-Agent = our BIC.
"""
import httpx

from http_util import call, request_headers
from reasons import XALI, XFMT, XNET, XTMO, Rejection

S = "i3-psp-desp/schemas/"


class DespClient:
    def __init__(self, me: str, bic: str, url: str, schemas):
        self.me, self.bic, self.url, self.schemas = me, bic, url.rstrip("/"), schemas
        self.client: httpx.AsyncClient | None = None  # set at start-up (app.py)

    async def _post(self, path: str, body: dict, req_schema: str, resp_schema: str, ok_status: int):
        self.schemas.check_outgoing(S + req_schema, body)
        try:
            status, _, resp = await call(self.client, self.me, "DESP", "POST", self.url, path, body,
                                         request_headers(self.bic))
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise Rejection(XNET)  # the DESP never got the message: safe to release what was reserved
        except httpx.HTTPError as e:
            # sent, but no (complete) answer: the DESP may have accepted it, so the outcome is unknown
            raise Rejection(XTMO, f"No answer from the DESP ({type(e).__name__})")
        if status != ok_status:
            return status, resp
        errors = self.schemas.errors(S + resp_schema, resp)
        if errors:
            raise Rejection(XFMT, f"DESP answer does not match the contract: {errors[0]['detail']}")
        return status, resp

    async def alias_lookup(self, alias: str, alias_type: str) -> tuple[str, str]:
        """PLACEHOLDER POST /v1/sim/alias-lookup (INTERPRETATION T5). Returns (DEAN, bank BIC)."""
        status, resp = await self._post("/v1/sim/alias-lookup", {"proxyAlias": alias, "proxyAliasType": alias_type},
                                        "placeholder/alias-lookup.request.schema.json",
                                        "placeholder/alias-lookup.response-200.schema.json", 200)
        if status == 404:
            raise Rejection(XALI)
        if status != 200:
            raise Rejection(XFMT, f"Alias lookup answered HTTP {status}")
        return resp["DEAN"], resp["digitalEuroPspId"]

    async def post_payment_instruction(self, body: dict) -> dict:
        """DESP API POST /v1/payment-instructions (D2-7 p.57–64). Returns the 201 body."""
        return await self._created("/v1/payment-instructions", body, "desp-api/post-payment-instructions")

    async def post_funding(self, kind: str, body: dict) -> dict:
        """DESP API POST /v1/fundings or /v1/defundings (D2-7 p.49–57). Returns the 201 body."""
        return await self._created(f"/v1/{kind}s", body, f"desp-api/post-{kind}s")

    async def _created(self, path, body, schema_base):
        status, resp = await self._post(path, body, schema_base + ".request.schema.json",
                                        schema_base + ".response-201.schema.json", 201)
        if status != 201:
            code = resp.get("reasonCode", XFMT) if isinstance(resp, dict) else XFMT
            raise Rejection(code, f"DESP answered HTTP {status}")
        return resp

"""Scenarios the game master can start from the control room (interface I7, ours).

Two kinds:
  - the example flows in /examples: the relay plays the banking app and sends
    the example's first message (I1) to the bank, exactly as in the example
    file, with fresh IDs and timestamps. The example's step titles and
    explanations go to the control room as the narration.
  - a free action: "<person> pays <person> <amount>", "<person> funds /
    defunds <amount>", built from the same example messages with other values.

Until real banking apps exist, the relay stands in for them. That stand-in is
marked in every event ("standIn": true), so nobody mistakes it for a real app.
"""
import copy
import glob
import json
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation


def _ts() -> str:
    t = datetime.now(timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


class ScenarioError(ValueError):
    pass


class Scenarios:
    def __init__(self, examples_dir: str, apps: dict):
        self.dir = examples_dir
        self.apps = apps
        self.by_name = {a["name"]: slug for slug, a in apps.items()}
        with open(os.path.join(examples_dir, "test-data.json"), encoding="utf-8") as f:
            self.test_data = json.load(f)
        self.flows = {}
        for folder in sorted(glob.glob(os.path.join(examples_dir, "*", ""))):
            flow = self._load_flow(folder.rstrip(os.sep))
            if flow:
                self.flows[flow["id"]] = flow
        self._counter = 0

    # ---------------------------------------------------------------- example flows

    def _load_flow(self, folder: str):
        files = sorted(glob.glob(os.path.join(folder, "[0-9][0-9]-*.json")))
        if not files:
            return None
        steps = []
        for path in files:
            with open(path, encoding="utf-8") as f:
                s = json.load(f)
            http = s.get("http") or {}
            steps.append({"step": s.get("step"), "file": os.path.basename(path), "title": s.get("title"),
                          "from": s.get("from"), "to": s.get("to"), "interface": s.get("interface"),
                          "method": http.get("method"), "path": http.get("path"), "status": http.get("status"),
                          "placeholder": bool(s.get("placeholder")), "specRef": s.get("specRef"),
                          "explanation": s.get("explanation"), "_body": s.get("body"),
                          "_headers": http.get("headers")})
        start = next((s for s in steps if s["path"] == "/i1/messages" and s["method"] == "POST"), None)
        if not start:
            return None
        title = os.path.basename(folder)
        readme = os.path.join(folder, "README.md")
        if os.path.exists(readme):
            with open(readme, encoding="utf-8") as f:
                first = f.readline().strip()
            if first.startswith("#"):
                title = first.lstrip("# ").strip()
        before = [s for s in steps if s["interface"] and s["interface"].startswith("I7") and s["step"] < start["step"]]
        return {"id": os.path.basename(folder), "title": title, "start": start, "gameMaster": before,
                "steps": [{k: v for k, v in s.items() if not k.startswith("_")} for s in steps]}

    def list(self) -> dict:
        users = [{"id": k, "name": u["name"], "bank": self.bank_slug(u["bank"])} for k, u in self.test_data["users"].items()]
        return {"examples": [{"id": f["id"], "title": f["title"]} for f in self.flows.values()],
                "people": users,
                "actions": ["pay", "fund", "defund"]}

    def bank_slug(self, test_data_bank: str) -> str:
        return next(slug for slug, a in self.apps.items() if a.get("testDataBank") == test_data_bank)

    def _fresh(self, body: dict, prefix: str) -> dict:
        """New MessageIdentification (max 35 characters) and current timestamps."""
        self._counter += 1
        body = copy.deepcopy(body)
        stamp = datetime.now(timezone.utc).strftime("%H%M%S")
        body["MessageIdentification"] = f"{prefix}-LIVE-{stamp}-{self._counter:04d}"[:35]
        now = _ts()
        for key in ("CreationDateTime", "TransactionDate"):
            if key in body:
                body[key] = now
        return body

    def example_call(self, flow_id: str) -> dict:
        flow = self.flows.get(flow_id)
        if not flow:
            raise ScenarioError(f"Unknown scenario {flow_id!r}")
        s = flow["start"]
        frm, to = self.by_name.get(s["from"]), self.by_name.get(s["to"])
        if not frm or not to:
            raise ScenarioError(f"Scenario {flow_id!r} uses apps the relay does not know: {s['from']} → {s['to']}")
        prefix = "APPA" if frm == "app-a" else "APPB"
        headers = {k: v for k, v in (s["_headers"] or {}).items() if k in ("Content-Type", "Sim-User-DEAN")}
        return {"id": flow_id, "title": flow["title"], "from": frm, "to": to, "path": s["path"],
                "headers": headers, "body": self._fresh(s["_body"], prefix), "steps": flow["steps"],
                "gameMaster": [{"title": g["title"], "body": g["_body"]} for g in flow["gameMaster"]]}

    # ---------------------------------------------------------------- free actions

    def _user(self, key: str) -> dict:
        u = self.test_data["users"].get(key)
        if not u:
            raise ScenarioError(f"Unknown person {key!r}")
        return u

    @staticmethod
    def _amount(value) -> float:
        try:
            a = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ScenarioError("Amount is not a number")
        if a <= 0 or a > Decimal("1000000") or a != a.quantize(Decimal("0.01")):
            raise ScenarioError("Amount must be positive, with at most two decimals")
        return float(a)  # I1 amounts are JSON numbers (INTERPRETATION C6)

    def _template(self, flow_id: str) -> dict:
        return copy.deepcopy(self.flows[flow_id]["start"]["_body"])

    def action_call(self, action: str, payer: str, amount, payee: str | None = None, text: str | None = None) -> dict:
        u = self._user(payer)
        bank = self.bank_slug(u["bank"])
        app = self.apps[bank]["app"]
        prefix = "APPA" if app == "app-a" else "APPB"
        amt = self._amount(amount)
        first = u["name"].split()[0]
        if action == "pay":
            if not payee:
                raise ScenarioError("Who should be paid?")
            p = self._user(payee)
            if p is u:
                raise ScenarioError("Payer and payee are the same person")
            body = self._template("p2p-two-psps")
            body.update({"Amount": amt, "Name": p["name"], "ProxyAccount": p["phone"], "ProxyAccountType": "TELE"})
            body["UnstructuredRemittanceInformation"] = (text or "Live payment")[:140]
            title = f"{first} pays {p['name'].split()[0]} {amt:.2f} EUR"
        elif action in ("fund", "defund"):
            body = self._template("funding-same-psp" if action == "fund" else "defunding-same-psp")
            body["DigitalEuroAccountNumber"] = u["dean"]
            if action == "fund":
                body.update({"DebtorAccount": u["iban"], "CreditorAccount": u["dean"]})
                title = f"{first} moves {amt:.2f} EUR from giro into digital euro (funding)"
            else:
                body.update({"DebtorAccount": u["dean"], "CreditorAccount": u["iban"]})
                title = f"{first} takes {amt:.2f} EUR back to giro (defunding)"
            body["Amount"] = amt
            body["UnstructuredRemittanceInformation"] = (text or "Live " + action + "ing")[:140]
        else:
            raise ScenarioError("Action must be pay, fund or defund")
        return {"id": f"live-{action}", "title": title, "from": app, "to": bank, "path": "/i1/messages",
                "headers": {"Content-Type": "application/json", "Sim-User-DEAN": u["dean"]},
                "body": self._fresh(body, prefix), "steps": [], "gameMaster": []}

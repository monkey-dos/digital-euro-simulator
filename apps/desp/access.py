"""Participant register and Access Management data of the DESP.

- Participant register (component map): which banks take part and where their
  PSP API lives. In the real scheme it is a list kept by the governing
  authority; here it is a config file (config/participants.json).
- Access Management (placeholder, INTERPRETATION T5 and C4): alias → DEAN and
  DEAN → (bank, ledger entry). No names: the DESP never stores them.

Both are seeded at start-up; the ledger balances come from the same seed file.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PARTICIPANTS = os.path.join(HERE, "config", "participants.json")
DEFAULT_SEED = os.path.join(HERE, "..", "..", "examples", "test-data.json")


class Participants:
    def __init__(self, path: str | None = None):
        path = path or os.environ.get("DESP_PARTICIPANTS") or DEFAULT_PARTICIPANTS
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.banks = {bic: v for bic, v in data["participants"].items()}

    def is_participant(self, bic: str) -> bool:
        return bic in self.banks

    def url(self, bic: str) -> str:
        return self.banks[bic]["pspApiUrl"].rstrip("/")

    def name(self, bic: str | None) -> str:
        return self.banks.get(bic, {}).get("name", bic or "unknown caller")


class AccessManagement:
    """PLACEHOLDER: the ECB spec for these registries is in a document we do not have."""

    def __init__(self):
        self.alias_to_dean: dict[tuple[str, str], str] = {}
        self.dean_to_account: dict[str, dict] = {}  # DEAN -> {"bic", "entryId"}

    def seed(self, users: dict, banks: dict):
        self.alias_to_dean.clear()
        self.dean_to_account.clear()
        for u in users.values():
            bic = banks[u["bank"]]["bic"]
            self.alias_to_dean[(u["phone"], "TELE")] = u["dean"]
            self.dean_to_account[u["dean"]] = {"bic": bic, "entryId": u["entry"]}

    def lookup_alias(self, alias: str, alias_type: str):
        """Returns (DEAN, bank BIC) or None."""
        dean = self.alias_to_dean.get((alias, alias_type))
        if dean is None:
            return None
        return dean, self.dean_to_account[dean]["bic"]

    def state(self) -> dict:
        return {
            "aliases": [{"proxyAlias": a, "proxyAliasType": t, "DEAN": d} for (a, t), d in sorted(self.alias_to_dean.items())],
            "deans": [{"DEAN": d, "bic": v["bic"], "entryId": v["entryId"]} for d, v in sorted(self.dean_to_account.items())],
        }


def load_seed(path: str | None = None) -> dict:
    path = path or os.environ.get("SIM_SEED") or DEFAULT_SEED
    with open(path, encoding="utf-8") as f:
        return json.load(f)

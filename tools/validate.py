#!/usr/bin/env python3
"""Validate every example message against its contract schema, plus rules a schema can't express."""
import base64
import glob
import json
import os
import sys

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_registry():
    reg, by_path = Registry(), {}
    for p in glob.glob(os.path.join(ROOT, "contracts", "**", "*.schema.json"), recursive=True):
        s = json.load(open(p))
        reg = reg.with_resource(s["$id"], Resource.from_contents(s))
        by_path[os.path.relpath(p, ROOT)] = s
    return reg, by_path


def dean_ok(d):
    s = d[4:] + d[:4]
    return int("".join(str(ord(c) - 55) if c.isalpha() else c for c in s)) % 97 == 1


def walk(o, key=None):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, k)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v, key)
    else:
        yield key, o


def get(o, dotted):
    for part in dotted.split("."):
        o = o[part]
    return o


def main():
    reg, schemas = load_registry()
    errors, count = [], 0
    for f in sorted(glob.glob(os.path.join(ROOT, "examples", "*", "*.json"))):
        rel = os.path.relpath(f, ROOT)
        m = json.load(open(f))
        count += 1
        body = m.get("body")
        if m.get("schema"):
            v = Draft202012Validator(schemas[m["schema"]], registry=reg, format_checker=FormatChecker())
            errors += [f"{rel}: {e.json_path}: {e.message}" for e in v.iter_errors(body)]
        dv = m.get("decryptedView")
        if dv:
            v = Draft202012Validator(schemas[dv["schema"]], registry=reg, format_checker=FormatChecker())
            errors += [f"{rel} (decrypted): {e.json_path}: {e.message}" for e in v.iter_errors(dv["content"])]
            try:
                blob = get(body, dv["field"])
                if json.loads(base64.b64decode(blob[len("SIMENC:"):])) != dv["content"]:
                    errors.append(f"{rel}: decryptedView does not match the encrypted field")
            except (KeyError, TypeError, ValueError):
                errors.append(f"{rel}: encrypted field {dv['field']} missing or not decodable")
        # DEAN check digits anywhere (body and decrypted view)
        for k, val in list(walk(body)) + list(walk(dv["content"] if dv else None)):
            if k == "DEAN" and isinstance(val, str) and not dean_ok(val):
                errors.append(f"{rel}: invalid DEAN check digits {val}")
        # conditional presence in DESP API POST /payment-instructions (Annex D2-7 p.59)
        if m.get("http", {}).get("path") == "/v1/payment-instructions" and m.get("from", "").startswith("PSP"):
            pio = (body or {}).get("paymentInstructionObject", {})
            same = pio.get("debtorAgent", {}).get("bicfi") == pio.get("creditorAgent", {}).get("bicfi")
            if same and "creditorEntry" not in pio:
                errors.append(f"{rel}: creditorEntry is mandatory when both users are at the same bank")
            if not same and "encryptedPaymentInstructionObject" not in pio:
                errors.append(f"{rel}: encryptedPaymentInstructionObject is mandatory between different banks")
            if not same and "defundingObject" in body:
                errors.append(f"{rel}: defundingObject only allowed when payer and payee share a bank")
    # ledger arithmetic
    for f in sorted(glob.glob(os.path.join(ROOT, "examples", "*", "*-ledger-settlement.json"))):
        total = 0
        for b in json.load(open(f))["body"]["bookings"]:
            from decimal import Decimal
            delta = sum(Decimal(x) for x in b["change"].split())
            if Decimal(b["before"]) + delta != Decimal(b["after"]):
                errors.append(f"{os.path.relpath(f, ROOT)}: booking for {b['entry']} doesn't add up")
            if Decimal(b["after"]) < 0:
                errors.append(f"{os.path.relpath(f, ROOT)}: negative balance for {b['entry']}")
            total += delta
        if total != 0:
            errors.append(f"{os.path.relpath(f, ROOT)}: bookings don't net to zero ({total})")
    for e in errors:
        print("FAIL", e)
    print(f"{count} example files checked, {len(errors)} problem(s).")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()

"""Validate message bodies against the JSON schemas in /contracts.

The contracts are the single source of truth for every message (CONTRIBUTING.md,
"contracts first"), so the app checks every body it receives and every body it
sends against them. Set CONTRACTS_DIR to use a different copy of /contracts.
"""
import glob
import json
import os
from decimal import Decimal

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

HERE = os.path.dirname(os.path.abspath(__file__))
CONTRACTS_DIR = os.environ.get("CONTRACTS_DIR") or os.path.join(HERE, "..", "..", "contracts")


class SchemaCheck:
    def __init__(self, contracts_dir: str = CONTRACTS_DIR):
        self.dir = os.path.abspath(contracts_dir)
        files = glob.glob(os.path.join(self.dir, "**", "*.schema.json"), recursive=True)
        if not files:
            raise SystemExit(f"No contract schemas found in {self.dir}. Set CONTRACTS_DIR to the repository's contracts/ folder.")
        registry, self.validators = Registry(), {}
        schemas = {}
        for path in files:
            # parse_float=Decimal so 'multipleOf: 0.01' works exactly (19.99 is not exact as a float)
            with open(path, encoding="utf-8") as f:
                schema = json.load(f, parse_float=Decimal)
            registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
            schemas[os.path.relpath(path, self.dir).replace(os.sep, "/")] = schema
        for rel, schema in schemas.items():
            self.validators[rel] = Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())

    def errors(self, schema: str, instance) -> list[dict]:
        """List of problems; empty if the instance is valid. `schema` is relative to contracts/."""
        validator = self.validators[schema]
        return [{"location": e.json_path, "detail": e.message[:300]} for e in validator.iter_errors(instance)]

    def check_outgoing(self, schema: str, instance) -> None:
        """Our own messages must be valid too. A failure here is a bug in this app."""
        problems = self.errors(schema, instance)
        if problems:
            raise RuntimeError(f"BUG: outgoing message violates {schema}: {problems}")

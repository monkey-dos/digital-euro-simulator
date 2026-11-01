# ADR 0006: Bank roles

Status: accepted (1 November 2026)

## Decision
PSP A serves private customers only. PSP B serves private and business customers and acts as acquiring bank. More banks can be added.

## Why
A payment from PSP A's customers to a shop always crosses banks, which shows the interesting path.

## Consequences
The bank app is one template, started with different configurations (name, BIC, customer types).

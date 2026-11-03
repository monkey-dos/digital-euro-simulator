"""Status reason codes used by the DESP (contracts/INTERPRETATION.md, choice C8).

Only a few codes are named in the ECB documents (D2-1): AC05, AC06, AB03, ARFR,
D002, D005. Everything starting with X is a PLACEHOLDER chosen by this project
(table at the end of INTERPRETATION.md).
"""
AB03 = "AB03"  # D2-1: settlement timeout. Here also: the payee bank did not answer in time.
D005 = "D005"  # D2-1: PSP is not a participant.
XFMT = "XFMT"  # placeholder: message format, schema or consistency error
XHDR = "XHDR"  # placeholder: technical header missing or invalid (INTERPRETATION T1)
XACC = "XACC"  # placeholder: ledger entry unknown, or not held via that bank
XBAL = "XBAL"  # placeholder: insufficient digital euro balance
XDCA = "XDCA"  # placeholder: the bank's DCA has not enough central bank money
XNSU = "XNSU"  # placeholder: not supported in this simulation (e.g. open funding, ADR 0001)
XFWD = "XFWD"  # placeholder: the other bank gave an invalid answer
XALI = "XALI"  # placeholder: alias not registered
XDUP = "XDUP"  # placeholder: UETR already used
XINT = "XINT"  # placeholder: internal error in this app (a bug)

TEXT = {
    AB03: "No answer from the other bank in time",
    D005: "Bank is not a participant",
    XFMT: "Message format error",
    XHDR: "Technical header missing or invalid",
    XACC: "Ledger entry unknown or held via another bank",
    XBAL: "Insufficient digital euro balance",
    XDCA: "Not enough central bank money on the bank's DCA",
    XNSU: "Not supported in this simulation",
    XFWD: "Invalid answer from the other bank",
    XALI: "Alias not registered",
    XDUP: "UETR already used",
    XINT: "Internal error",
}


def status_reason(code: str, info: str | None = None) -> dict:
    """StatusReason object (common/types.schema.json): statusReasonCode + optional text (max 140)."""
    reason = {"statusReasonCode": code}
    text = info or TEXT.get(code)
    if text:
        reason["statusReasonAdditionalInformation"] = text[:140]
    return reason


class Rejection(Exception):
    """A business rejection with a reason code (C8)."""

    def __init__(self, code: str, info: str | None = None, payee_rejected: bool = False):
        super().__init__(f"{code}: {info or TEXT.get(code, '')}")
        self.code, self.info = code, info
        self.payee_rejected = payee_rejected  # True if the payee bank itself said no (Fig. 8)

    def reason(self) -> dict:
        return status_reason(self.code, self.info)

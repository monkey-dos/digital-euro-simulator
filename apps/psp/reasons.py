"""Status reason codes used by the bank (contracts/INTERPRETATION.md, choice C8).

Codes from the ECB documents: AB03, AC05, AC06, D005. Everything starting with X
is a PLACEHOLDER chosen by this project (table at the end of INTERPRETATION.md).
The same codes go to the banking app as StatusReason (I1, INTERPRETATION A13).
"""
XFMT = "XFMT"  # message format, schema or consistency error
XHDR = "XHDR"  # technical header missing or invalid (T1)
XAUT = "XAUT"  # no logged-in user on I1 (A12)
XACC = "XACC"  # account unknown, or not at this bank
XBAL = "XBAL"  # balance too low (digital euro + giro where reverse waterfall applies)
XLIM = "XLIM"  # funding would exceed the holding limit
XNSU = "XNSU"  # not supported in this simulation
XALI = "XALI"  # alias not registered
XNET = "XNET"  # the bank could not reach the DESP
XTMO = "XTMO"  # no final status from the DESP in time
XINT = "XINT"  # internal error in this app (a bug)

TEXT = {
    XFMT: "Message format error",
    XHDR: "Technical header missing or invalid",
    XAUT: "No logged-in user",
    XACC: "Account unknown or not at this bank",
    XBAL: "Insufficient funds",
    XLIM: "Holding limit would be exceeded",
    XNSU: "Not supported in this simulation",
    XALI: "Alias not registered",
    XNET: "Central platform not reachable",
    XTMO: "No final status in time",
    XINT: "Internal error",
}


def status_reason(code: str, info: str | None = None) -> dict:
    """StatusReason object (common/types.schema.json) for I3 messages."""
    reason = {"statusReasonCode": code}
    text = info or TEXT.get(code)
    if text:
        reason["statusReasonAdditionalInformation"] = text[:140]
    return reason


class Rejection(Exception):
    """A business rejection: reaches the app as ReturnCode 1 + StatusReason (A13)."""

    def __init__(self, code: str, info: str | None = None):
        super().__init__(f"{code}: {info or TEXT.get(code, '')}")
        self.code, self.info = code, info

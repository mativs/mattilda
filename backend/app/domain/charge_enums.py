from enum import Enum


class ChargeType(str, Enum):
    fee = "fee"
    interest = "interest"
    penalty = "penalty"
    balance_forward = "balance_forward"


class ChargeStatus(str, Enum):
    unbilled = "unbilled"
    billed = "billed"
    cancelled = "cancelled"

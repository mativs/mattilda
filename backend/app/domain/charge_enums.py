from enum import Enum


class ChargeType(str, Enum):
    fee = "fee"
    interest = "interest"
    penalty = "penalty"


class ChargeStatus(str, Enum):
    paid = "paid"
    unpaid = "unpaid"
    cancelled = "cancelled"

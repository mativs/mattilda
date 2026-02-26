from enum import Enum


class FeeRecurrence(str, Enum):
    monthly = "monthly"
    annual = "annual"
    one_time = "one_time"

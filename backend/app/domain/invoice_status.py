from enum import Enum


class InvoiceStatus(str, Enum):
    open = "open"
    closed = "closed"
    cancelled = "cancelled"

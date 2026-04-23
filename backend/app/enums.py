import enum


class WarehouseType(str, enum.Enum):
    MAIN = "MAIN"
    BRANCH = "BRANCH"
    TRANSIT = "TRANSIT"
    QUARANTINE = "QUARANTINE"


class CustomerType(str, enum.Enum):
    B2B = "B2B"
    B2C = "B2C"


class POStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    PARTIAL_RECEIVED = "PARTIAL_RECEIVED"
    FULLY_RECEIVED = "FULLY_RECEIVED"
    CANCELLED = "CANCELLED"


class POSource(str, enum.Enum):
    MANUAL = "MANUAL"
    OCR = "OCR"
    IMPORT = "IMPORT"
    API = "API"


class SOStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    PARTIAL_SHIPPED = "PARTIAL_SHIPPED"
    FULLY_SHIPPED = "FULLY_SHIPPED"
    INVOICED = "INVOICED"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class GRStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class DOStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class InvoiceType(str, enum.Enum):
    INVOICE = "INVOICE"
    SELF_BILLED = "SELF_BILLED"
    CONSOLIDATED = "CONSOLIDATED"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    VALIDATED = "VALIDATED"
    FINAL = "FINAL"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class RejectedBy(str, enum.Enum):
    LHDN = "LHDN"
    BUYER = "BUYER"


class CreditNoteStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    VALIDATED = "VALIDATED"
    FINAL = "FINAL"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class CreditNoteReason(str, enum.Enum):
    RETURN = "RETURN"
    DISCOUNT_ADJUSTMENT = "DISCOUNT_ADJUSTMENT"
    PRICE_CORRECTION = "PRICE_CORRECTION"
    WRITE_OFF = "WRITE_OFF"
    OTHER = "OTHER"


class PaymentDirection(str, enum.Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    FPX = "FPX"
    DUITNOW = "DUITNOW"
    CREDIT_CARD = "CREDIT_CARD"
    CHEQUE = "CHEQUE"
    OTHER = "OTHER"


class RoleCode(str, enum.Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    SALES = "SALES"
    PURCHASER = "PURCHASER"


class CostingMethod(str, enum.Enum):
    WEIGHTED_AVERAGE = "WEIGHTED_AVERAGE"
    FIFO = "FIFO"
    SPECIFIC = "SPECIFIC"


class StockMovementType(str, enum.Enum):
    PURCHASE_IN = "PURCHASE_IN"
    PURCHASE_RETURN = "PURCHASE_RETURN"
    SALES_OUT = "SALES_OUT"
    SALES_RETURN = "SALES_RETURN"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"
    ADJUSTMENT_IN = "ADJUSTMENT_IN"
    ADJUSTMENT_OUT = "ADJUSTMENT_OUT"
    RESERVE = "RESERVE"
    UNRESERVE = "UNRESERVE"
    QUALITY_HOLD = "QUALITY_HOLD"
    QUALITY_RELEASE = "QUALITY_RELEASE"


class StockMovementSourceType(str, enum.Enum):
    PO = "PO"
    SO = "SO"
    GR = "GR"
    DO = "DO"
    CN = "CN"
    TRANSFER = "TRANSFER"
    ADJUSTMENT = "ADJUSTMENT"
    OPENING = "OPENING"
    DEMO_RESET = "DEMO_RESET"


class StockTransferStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    IN_TRANSIT = "IN_TRANSIT"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


class StockAdjustmentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class StockAdjustmentReason(str, enum.Enum):
    PHYSICAL_COUNT = "PHYSICAL_COUNT"
    DAMAGE = "DAMAGE"
    THEFT = "THEFT"
    CORRECTION = "CORRECTION"
    EXPIRY = "EXPIRY"
    OTHER = "OTHER"


class TaxType(str, enum.Enum):
    SALES_TAX = "SALES_TAX"
    SERVICE_TAX = "SERVICE_TAX"
    EXEMPT = "EXEMPT"


class NotificationType(str, enum.Enum):
    LOW_STOCK = "LOW_STOCK"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    EINVOICE_VALIDATED = "EINVOICE_VALIDATED"
    EINVOICE_REJECTED = "EINVOICE_REJECTED"
    EINVOICE_EXPIRING = "EINVOICE_EXPIRING"
    PAYMENT_RECEIVED = "PAYMENT_RECEIVED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    DEMO_RESET_DONE = "DEMO_RESET_DONE"
    OTHER = "OTHER"


class NotificationSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AuditAction(str, enum.Enum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    DELETED = "DELETED"
    RESTORED = "RESTORED"
    STATUS_CHANGED = "STATUS_CHANGED"
    APPROVED = "APPROVED"
    CANCELLED = "CANCELLED"
    SUBMITTED = "SUBMITTED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    FINALIZED = "FINALIZED"


class AIFeature(str, enum.Enum):
    OCR_INVOICE = "OCR_INVOICE"
    EINVOICE_PRECHECK = "EINVOICE_PRECHECK"
    DASHBOARD_SUMMARY = "DASHBOARD_SUMMARY"
    OTHER = "OTHER"


class AICallStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    DISABLED = "DISABLED"


class FileCategory(str, enum.Enum):
    OCR_INVOICE = "OCR_INVOICE"
    EINVOICE_PDF = "EINVOICE_PDF"
    AVATAR = "AVATAR"
    LOGO = "LOGO"
    IMPORT_EXCEL = "IMPORT_EXCEL"
    REJECTION_ATTACHMENT = "REJECTION_ATTACHMENT"
    OTHER = "OTHER"


class DemoResetTrigger(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"


class DemoResetStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    ROLLED_BACK = "ROLLED_BACK"

# Import order follows FK dependency graph so Alembic autogenerate sees all tables.
# organization → master → sku → partner → purchase → sales → invoice → stock → audit

from app.models.organization import (  # noqa: F401
    Organization,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
    Warehouse,
)
from app.models.master import (  # noqa: F401
    Brand,
    Category,
    Currency,
    ExchangeRate,
    MSICCode,
    TaxRate,
    UOM,
)
from app.models.sku import SKU  # noqa: F401
from app.models.partner import Customer, Supplier  # noqa: F401
from app.models.purchase import (  # noqa: F401
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
)
from app.models.sales import (  # noqa: F401
    DeliveryOrder,
    DeliveryOrderLine,
    SalesOrder,
    SalesOrderLine,
)
from app.models.invoice import (  # noqa: F401
    CreditNote,
    CreditNoteLine,
    Invoice,
    InvoiceLine,
    Payment,
    PaymentAllocation,
)
from app.models.stock import (  # noqa: F401
    Stock,
    StockAdjustment,
    StockAdjustmentLine,
    StockMovement,
    StockTransfer,
    StockTransferLine,
)
from app.models.audit import (  # noqa: F401
    AICallLog,
    AuditLog,
    DemoResetLog,
    DocumentSequence,
    LoginAttempt,
    Notification,
    UploadedFile,
)

__all__ = [
    # organization
    "Organization", "User", "Role", "Permission", "RolePermission", "UserRole", "Warehouse",
    # master
    "Currency", "ExchangeRate", "TaxRate", "UOM", "Brand", "Category", "MSICCode",
    # sku
    "SKU",
    # partner
    "Supplier", "Customer",
    # purchase
    "PurchaseOrder", "PurchaseOrderLine", "GoodsReceipt", "GoodsReceiptLine",
    # sales
    "SalesOrder", "SalesOrderLine", "DeliveryOrder", "DeliveryOrderLine",
    # invoice
    "Invoice", "InvoiceLine", "CreditNote", "CreditNoteLine", "Payment", "PaymentAllocation",
    # stock
    "Stock", "StockMovement", "StockTransfer", "StockTransferLine",
    "StockAdjustment", "StockAdjustmentLine",
    # audit
    "DocumentSequence", "Notification", "AuditLog", "AICallLog",
    "UploadedFile", "LoginAttempt", "DemoResetLog",
]

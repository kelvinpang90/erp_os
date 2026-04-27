from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.enums import CustomerType


class CustomerCreate(BaseModel):
    code: str = Field(..., max_length=32)
    name: str = Field(..., max_length=200)
    name_zh: Optional[str] = Field(None, max_length=200)
    customer_type: CustomerType = CustomerType.B2B
    registration_no: Optional[str] = Field(None, max_length=64)
    tin: Optional[str] = Field(None, max_length=16)
    sst_registration_no: Optional[str] = Field(None, max_length=32)
    msic_code: Optional[str] = Field(None, max_length=8)
    contact_person: Optional[str] = Field(None, max_length=120)
    email: Optional[str] = Field(None, max_length=120)
    phone: Optional[str] = Field(None, max_length=32)
    address_line1: Optional[str] = Field(None, max_length=200)
    address_line2: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=80)
    state: Optional[str] = Field(None, max_length=80)
    postcode: Optional[str] = Field(None, max_length=16)
    country: str = Field("MY", max_length=2)
    currency: str = Field("MYR", max_length=3)
    payment_terms_days: int = Field(30, ge=0)
    credit_limit: Decimal = Field(Decimal("0"), ge=Decimal("0"))
    notes: Optional[str] = None


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    name_zh: Optional[str] = Field(None, max_length=200)
    customer_type: Optional[CustomerType] = None
    registration_no: Optional[str] = Field(None, max_length=64)
    tin: Optional[str] = Field(None, max_length=16)
    sst_registration_no: Optional[str] = Field(None, max_length=32)
    msic_code: Optional[str] = Field(None, max_length=8)
    contact_person: Optional[str] = Field(None, max_length=120)
    email: Optional[str] = Field(None, max_length=120)
    phone: Optional[str] = Field(None, max_length=32)
    address_line1: Optional[str] = Field(None, max_length=200)
    address_line2: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=80)
    state: Optional[str] = Field(None, max_length=80)
    postcode: Optional[str] = Field(None, max_length=16)
    country: Optional[str] = Field(None, max_length=2)
    currency: Optional[str] = Field(None, max_length=3)
    payment_terms_days: Optional[int] = Field(None, ge=0)
    credit_limit: Optional[Decimal] = Field(None, ge=Decimal("0"))
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class CustomerResponse(BaseModel):
    id: int
    organization_id: int
    code: str
    name: str
    name_zh: Optional[str]
    customer_type: CustomerType
    contact_person: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    country: str
    currency: str
    payment_terms_days: int
    credit_limit: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, json_encoders={Decimal: str})


class CustomerDetail(CustomerResponse):
    registration_no: Optional[str]
    tin: Optional[str]
    sst_registration_no: Optional[str]
    msic_code: Optional[str]
    address_line1: Optional[str]
    address_line2: Optional[str]
    city: Optional[str]
    state: Optional[str]
    postcode: Optional[str]
    notes: Optional[str]
    created_by: Optional[int]
    updated_by: Optional[int]

    model_config = ConfigDict(from_attributes=True, json_encoders={Decimal: str})

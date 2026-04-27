from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.enums import WarehouseType


class WarehouseCreate(BaseModel):
    code: str = Field(..., max_length=32)
    name: str = Field(..., max_length=200)
    type: WarehouseType = WarehouseType.BRANCH
    address_line1: Optional[str] = Field(None, max_length=200)
    address_line2: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=80)
    state: Optional[str] = Field(None, max_length=80)
    postcode: Optional[str] = Field(None, max_length=16)
    country: str = Field("MY", max_length=2)
    phone: Optional[str] = Field(None, max_length=32)
    manager_user_id: Optional[int] = None


class WarehouseUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    type: Optional[WarehouseType] = None
    address_line1: Optional[str] = Field(None, max_length=200)
    address_line2: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=80)
    state: Optional[str] = Field(None, max_length=80)
    postcode: Optional[str] = Field(None, max_length=16)
    country: Optional[str] = Field(None, max_length=2)
    phone: Optional[str] = Field(None, max_length=32)
    manager_user_id: Optional[int] = None
    is_active: Optional[bool] = None


class WarehouseResponse(BaseModel):
    id: int
    organization_id: int
    code: str
    name: str
    type: WarehouseType
    city: Optional[str]
    state: Optional[str]
    country: str
    phone: Optional[str]
    manager_user_id: Optional[int]
    manager_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WarehouseDetail(WarehouseResponse):
    address_line1: Optional[str]
    address_line2: Optional[str]
    postcode: Optional[str]

    model_config = ConfigDict(from_attributes=True)

from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

"""用户"""
# 创建
class CreateUser(BaseModel):
    username: str
    password: str

# 响应
class UserOut(BaseModel):
    id: int
    username: str

"""token认证"""
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: int
    user_role: str

"""供应商"""
# 创建
class SupplierCreate(BaseModel):
    name: str
    contact: Optional[str] = None
    phone: Optional[str] = None

# 响应
class SupplierOut(SupplierCreate):
    id: int

# 更新
class SupplierUpdate(SupplierCreate):
    status: Optional[int] = None
    sort_order: Optional[int] = None


# 分类
class CategoryCreate(BaseModel):
    name: str
    parent_id: int
    sort_order: Optional[int] = None
    status: Optional[int] = None

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None
    status: Optional[int] = None


# 库存
class InventoryOut(BaseModel):
    id: int
    code: int
    name: str
    type: str
    stock: int
    unit: str
    warning: Optional[int] = None
    mnemonic_code: Optional[str] = None   # 助记码，前端列表展示与搜索需要


# 库存分页响应
class InventoryPage(BaseModel):
    total: int
    items: List[InventoryOut]


class InventoryCreate(BaseModel):
    mnemonic_code: Optional[str] = None
    supplier_id: int
    category_id: int
    name: str
    type: Optional[str] = None
    stock: int
    unit: str
    warning: Optional[int] = None
    status: Optional[int] = None

class InventoryUpdate(BaseModel):
    mnemonic_code: Optional[str] = None
    supplier_id: Optional[int] = None
    category_id: Optional[int] = None
    name: Optional[str] = None
    type: Optional[str] = None
    stock: Optional[int] = None
    unit: Optional[str] = None
    warning: Optional[int] = None
    status: Optional[int] = None


# 搜索
class OrderSearchInventory(BaseModel):
    id: int
    code: str
    name: str
    type: Optional[str] = None
    unit: Optional[str] = ''
    stock: Optional[int] = 0
    model_config = {"from_attributes": True}


# 流水
# 注意: 查询用了 isouter join, 物料缺失时 name/type/unit 可能为 None, 必须 Optional
class RecordOut(BaseModel):
    transaction_date: datetime
    name: Optional[str] = None
    type: Optional[str] = None
    unit: Optional[str] = None
    order_type: Optional[int] = None
    before_quantity: Optional[int] = None
    change_quantity: Optional[int] = None
    after_quantity: Optional[int] = None


# 流水分页响应
class RecordPage(BaseModel):
    total: int
    items: List[RecordOut]


# 单据列表
class OrderListOut(BaseModel):
    id: int
    order_no: str
    order_type: int
    transaction_date: datetime
    status: Optional[int] = None
    supplier_id: Optional[int] = None
    remark: Optional[str] = None
    created_by: str


# 单据列表分页响应
class OrderListPage(BaseModel):
    total: int
    items: List[OrderListOut]

# 单据明细
class OrderItemOut(BaseModel):
    item_code: str
    item_name: str
    item_type: str
    item_unit: str
    inventory_id: int
    quantity: int
    price: Optional[float] = None
    unit_price: Optional[float] = None
    total_amount: Optional[float] = None
    line_remark: Optional[str] = None

# 单据
class OrderOut(BaseModel):
    id: int
    order_no: str
    order_type: int
    transaction_date: datetime
    status: Optional[int] = None
    supplier_id: Optional[int] = None
    remark: Optional[str] = None
    created_by: str
    items: List[OrderItemOut]



class OrderItemCreate(BaseModel):
    inventory_id: int
    quantity: int
    price: Optional[float] = None
    line_remark: Optional[str] = None


class OrderCreate(BaseModel):
    order_type: int
    transaction_date: Optional[datetime] = None
    supplier_id: Optional[int] = None
    remark: Optional[str] = None
    items: List[OrderItemCreate] 

class OrderItemUpdate(BaseModel):
    inventory_id: int
    quantity: int
    price: Optional[float] = None
    line_remark: Optional[str] = None

class OrderUpdate(BaseModel):
    order_type: Optional[int] = None
    supplier_id: Optional[int] = None
    transaction_date: Optional[datetime] = None
    remark: Optional[str] = None
    items: Optional[List[OrderItemUpdate]] = None   # 如果传了 items 则全量替换
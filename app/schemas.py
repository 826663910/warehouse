from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

"""用户"""
# 创建
class CreateUser(BaseModel):
    username: str
    password: str
    level: int = 1   # 1=普通用户 2=管理员 3=超级管理员（role 由后端从 level 派生，不收前端值）


# 更新用户（改密码 / 改级别；都可选，只改传了的）
class UserUpdate(BaseModel):
    password: Optional[str] = None
    level: Optional[int] = None


# 响应
class UserOut(BaseModel):
    id: int
    username: str
    role: Optional[str] = None
    level: int = 1
    created_at: Optional[datetime] = None

"""token认证"""
class Token(BaseModel):
    access_token: str
    token_type: str
    level: Optional[int] = None      # 登录后前端凭这个决定是否显示"账号管理"菜单
    username: Optional[str] = None

class TokenData(BaseModel):
    user_id: int
    user_role: str

"""供应商"""
# 创建
class SupplierCreate(BaseModel):
    name: str
    contact: Optional[str] = None
    phone: Optional[str] = None
    created_at: Optional[datetime] = None

# 响应
class SupplierOut(SupplierCreate):
    id: int

# 更新
class SupplierUpdate(SupplierCreate):
    status: Optional[int] = None
    sort_order: Optional[int] = None

"""分类"""
# 创建
class CategoryCreate(BaseModel):
    name: str
    parent_id: int
    sort_order: Optional[int] = None
    status: Optional[int] = None

# 更新
class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None
    status: Optional[int] = None

"""客户"""
# 响应
class CustomerOut(BaseModel):
    id: int
    name: str
    contact: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime

# 创建
class CustomerCreate(BaseModel):
    name: str
    contact: Optional[str] = None
    phone: Optional[str] = None
    sort_order: Optional[int] = None

# 更新
class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    contact: Optional[str] = None
    phone: Optional[str] = None
    sort_order: Optional[int] = None


"""大小包装"""
class PackageOut(BaseModel):
    id: int
    unit_name: str
    qty_per_base: int
        

class PackageCreate(BaseModel):
    unit_name: str
    qty_per_base: int
    

"""库存"""
# 响应
class InventoryOut(BaseModel):
    id: int
    code: str                             
    name: str
    type: Optional[str] = None             
    stock: int   # 基础单位（排序/比较用，不直接展示）
    stock_display: Optional[float] = None  # 展示用
    unit: Optional[str] = None             # 显示用单位
    unit_base: Optional[str] = None
    unit_category: Optional[str] = None
    warning: Optional[int] = None   # 基础单位数量预警值
    warning_display: Optional[float] = None  # 展示用的预警值
    # 移动加权平均成本：由入库单审核时自动重算，前端只读展示（不可编辑、不可提交）
    avg_cost: Optional[float] = None
    mnemonic_code: Optional[str] = None   # 助记码，前端列表展示与搜索需要
    # 列表展示用：分类路径 = 「一级分类/末级分类」（仅一级时只显示末级），供应商名称
    category_path: Optional[str] = None
    supplier_name: Optional[str] = None
    # 物料状态：1 启用 / 0 禁用（前端列表展示 + 筛选）
    status: Optional[int] = None
    
# 库存分页响应
class InventoryPage(BaseModel):
    total: int
    items: List[InventoryOut]

# 库存详情（编辑页）：在列表字段基础上多一层包装规格
# ⚠️ 必须用响应模型，不能直接 return ORM 对象：
#    selectinload 加载 packages 时 back_populates 会把 pkg.inventory 指回父对象，
#    jsonable_encoder 递归序列化会 RecursionError。Pydantic 只输出声明的字段，天然避开。
class InventoryDetail(InventoryOut):
    # 列表专用的两个展示字段，编辑页用不到 → exclude 掉不输出
    category_path: Optional[str] = Field(default=None, exclude=True)
    supplier_name: Optional[str] = Field(default=None, exclude=True)
    category_id: Optional[int] = None
    supplier_id: Optional[int] = None
    packages: List[PackageOut] = []


# 库存创建
class InventoryCreate(BaseModel):
    mnemonic_code: Optional[str] = None
    supplier_id: int
    category_id: int
    name: str
    type: Optional[str] = None
    stock: int
    unit_category: str  # 单位类型
    unit: str           # 显示用单位
    warning: Optional[int] = None
    status: Optional[int] = None
    packages: Optional[List[PackageCreate]] = None

# 库存信息更新
class InventoryUpdate(BaseModel):
    mnemonic_code: Optional[str] = None
    supplier_id: Optional[int] = None
    category_id: Optional[int] = None
    name: Optional[str] = None
    unit: Optional[str] = None
    unit_category: Optional[str] = None  # 必须可选：PATCH 是局部更新，不带就不能要求必填
    stock: Optional[int] = None
    warning: Optional[int] = None
    status: Optional[int] = None
    packages: Optional[List[PackageCreate]] = None


"""单据中搜索物料"""
class OrderSearchInventory(BaseModel):
    id: int
    code: str
    name: str
    type: Optional[str] = None
    unit: Optional[str] = ''
    stock: Optional[int] = 0
    stock_display: Optional[float] = 0.0
    # 单位换算：开单时前端要按 unit_category 拉可选单位，才能把"5 斤"换算成库存数
    unit_category: Optional[str] = None
    unit_base: Optional[str] = None
    # 当前库存均价：单据编辑页展示「参考成本」「预计毛利」用
    avg_cost: Optional[float] = None
    # 展示用：分类路径 + 当前供应商名（与 InventoryOut 一致）
    category_path: Optional[str] = None
    supplier_name: Optional[str] = None
    # 包装规格（大小件）：开单要能按「箱 / 盒」录入，后端按 qty_per_base 换算成基础单位
    packages: List[PackageOut] = []
    model_config = {"from_attributes": True}


"""流水"""
# 注意: 查询用了 isouter join, 物料缺失时 name/type/unit 可能为 None, 必须 Optional
class RecordOut(BaseModel):
    transaction_date: datetime
    code: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    unit: Optional[str] = None
    order_type: Optional[int] = None
    before_quantity: Optional[int] = None   # 储存用
    change_quantity: Optional[int] = None
    after_quantity: Optional[int] = None
    before_display: Optional[float] = None   # 显示用（基础单位 → 显示单位，不落库）
    change_display: Optional[float] = None
    after_display: Optional[float] = None
    # 成本快照：本笔流水发生时的单位成本（入库=采购价；出库/退货/报废=当时库存均价）
    # 前端用它展示「成本金额 = |变更数量| × 成本单价」
    unit_cost: Optional[float] = None
    # 订单明细的单价（join stock_order_details 出来）：出库/退货=销售/退货价；入库/报废前端不用
    # 配 unit_cost 一起，前端能展示「销售/退货金额 + 成本 + 毛利」三件套
    unit_price: Optional[float] = None
    # 来源单据 ID：前端点击流水行跳转单据详情用
    order_id: Optional[int] = None


# 流水分页响应
class RecordPage(BaseModel):
    total: int
    items: List[RecordOut]


"""报表"""
# 报表：按物料聚合的出入库汇总（每行 = 一个物料在筛选范围内的汇总）
class ReportOut(BaseModel):
    code: Optional[str] = None          # 物料编码
    name: Optional[str] = None          # 物料名称
    type: Optional[str] = None          # 型号
    unit: Optional[str] = None          # 单位
    tx_count: Optional[int] = None      # 流水笔数
    total_in: Optional[int] = None      # 入库总量（正数部分之和）
    total_out: Optional[int] = None     # 出库总量（负数部分之和，负值）
    total_ret: Optional[int] = None     # 退货总量（order_type=3，负值）
    total_scr: Optional[int] = None     # 报废总量（order_type=4，负值）
    net_change: Optional[int] = None    # 净变化 = 入 + 出 + 退 + 报废 四个口径之和
    last_date: Optional[datetime] = None  # 最近一次交易时间
    # 展示用：上面 5 个总量从【基础单位】换算成【本行物料的显示单位】（不落库）
    total_in_display: Optional[float] = None
    total_out_display: Optional[float] = None
    total_ret_display: Optional[float] = None
    total_scr_display: Optional[float] = None
    net_change_display: Optional[float] = None


# 报表汇总：按【单位赛道】分行（不同赛道的量纲不同，不能相加）
class ReportCategorySummary(BaseModel):
    category: Optional[str] = None      # 赛道：weight / length / volume / count / other
    unit: Optional[str] = None          # 该赛道汇总用的目标单位：公斤 / 米 / 升 / 个
    tx_count: Optional[int] = None      # 该赛道流水笔数
    item_count: Optional[int] = None    # 该赛道涉及物料数
    total_in: Optional[float] = None    # 以下 5 项已换算到该赛道的 unit
    total_out: Optional[float] = None
    total_ret: Optional[float] = None
    total_scr: Optional[float] = None
    net_change: Optional[float] = None


# 报表汇总（当前筛选范围内的总计，与分页无关）
# ⚠️ 不再提供跨赛道的 total_in/out/... —— 斤 + 米 + 个 加不出任何有意义的数
class ReportSummary(BaseModel):
    tx_count: Optional[int] = None      # 流水总笔数（纯计数，与单位无关）
    item_count: Optional[int] = None    # 涉及物料数（纯计数）
    by_category: List[ReportCategorySummary] = []


# 报表分页响应
class ReportPage(BaseModel):
    total: int
    items: List[ReportOut]
    summary: Optional[ReportSummary] = None


"""毛利报表"""
# 单月毛利
class ProfitMonthOut(BaseModel):
    month: str                          # '2026-10'
    revenue: float                      # 收入 = 该月【已审核出库单】的金额合计
    cost: float                         # 成本 = 该月出库数量 × 审核那一刻的成本快照
    profit: float                       # 毛利 = 收入 - 成本
    profit_rate: Optional[float] = None # 毛利率 %（收入为 0 时给 None，避免除零）

# 汇总：与按月明细同口径，只是把筛选范围内的月份全加起来
class ProfitSummary(BaseModel):
    revenue: float
    cost: float
    profit: float
    profit_rate: Optional[float] = None

# 按月趋势响应
class ProfitTrendOut(BaseModel):
    items: List[ProfitMonthOut]
    total: ProfitSummary


"""单据"""
# 单据列表
class OrderListOut(BaseModel):
    id: int
    order_no: str
    order_type: int
    transaction_date: datetime
    status: Optional[int] = None
    supplier_id: Optional[int] = None
    customer_id: Optional[int] = None
    remark: Optional[str] = None
    created_by: str

# 单据列表分页响应
class OrderListPage(BaseModel):
    total: int
    items: List[OrderListOut]


# 单据明细
class OrderItemOut(BaseModel):
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    item_type: Optional[str] = None
    item_unit: Optional[str] = None
    inventory_id: int
    quantity: int                      # 基础单位（库存数学用，不直接展示）
    quantity_display: Optional[float] = None  # 展示用
    input_qty: Optional[float] = None  # 用户录入的数量（按 input_unit 计）
    input_unit: Optional[str] = None   # 用户录入的单位（斤/公斤/个...）
    price: Optional[float] = None
    unit_price: Optional[float] = None
    total_amount: Optional[float] = None
    line_remark: Optional[str] = None
    # 展示用：通过 inventory_id 现算的「一级/末级」分类路径 + 当前供应商名
    category_path: Optional[str] = None
    supplier_name: Optional[str] = None

# 单据
class OrderOut(BaseModel):
    id: int
    order_no: str
    order_type: int
    transaction_date: datetime
    status: Optional[int] = None
    supplier_id: Optional[int] = None
    customer_id: Optional[int] = None
    remark: Optional[str] = None
    created_by: str
    items: List[OrderItemOut]


# 创建
class OrderItemCreate(BaseModel):
    inventory_id: int
    input_qty: Optional[float] = None   # 推荐：用户按 input_unit 录入的数量
    input_unit: Optional[str] = None    # 不传则用物料的显示单位
    quantity: Optional[int] = None      # 【兼容旧前端】直接给基础单位数量，前端改完后可删
    price: Optional[Decimal] = None
    line_remark: Optional[str] = None

class OrderCreate(BaseModel):
    order_type: int
    transaction_date: Optional[datetime] = None
    supplier_id: Optional[int] = None
    customer_id: Optional[int] = None
    remark: Optional[str] = None
    items: List[OrderItemCreate] 


# 更新
class OrderItemUpdate(BaseModel):
    inventory_id: int
    input_qty: Optional[float] = None   # 推荐：用户按 input_unit 录入的数量
    input_unit: Optional[str] = None    # 不传则用物料的显示单位
    quantity: Optional[int] = None      # 【兼容旧前端】直接给基础单位数量，前端改完后可删
    price: Optional[Decimal] = None
    line_remark: Optional[str] = None

class OrderUpdate(BaseModel):
    order_type: Optional[int] = None
    supplier_id: Optional[int] = None
    customer_id: Optional[int] = None
    transaction_date: Optional[datetime] = None
    remark: Optional[str] = None
    items: Optional[List[OrderItemUpdate]] = None   # 如果传了 items 则全量替换


"""仪表盘（首页聚合统计）"""
# 按【单位赛道】分组的总量（不同赛道量纲不同，不能相加）
class DashCategoryTotal(BaseModel):
    category: Optional[str] = None   # 赛道：weight / length / volume / count / other
    unit: Optional[str] = None       # 该赛道汇总用的目标单位：公斤 / 米 / 升 / 个
    total: Optional[float] = None


# 预警物料（库存 <= 预警线）
class DashWarningItem(BaseModel):
    id: Optional[int] = None      # 前端列表 :key 用
    code: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    unit: Optional[str] = None
    stock: Optional[int] = None
    warning: Optional[int] = None
    # 展示用：基础单位 → 显示单位（后端临时换算，不落库）
    stock_display: Optional[float] = None
    warning_display: Optional[float] = None


# 最近流水（字段与流水页对齐，只取展示需要的）
class DashRecentRecord(BaseModel):
    transaction_date: datetime
    name: Optional[str] = None
    type: Optional[str] = None
    unit: Optional[str] = None
    order_type: int
    change_quantity: int
    after_quantity: int
    # 展示用：同上，换算成显示单位
    change_display: Optional[float] = None
    after_display: Optional[float] = None


# 趋势点：近 N 天 × 某单据类型 × 【某单位赛道】的总量（绝对值）
# 带 category / unit：同一天不同赛道的值画不到一根 Y 轴上，前端按赛道切换
class DashTrendPoint(BaseModel):
    day: str             # 'YYYY-MM-DD'
    order_type: int
    quantity: float      # 已换算到该赛道的 unit
    category: Optional[str] = None
    unit: Optional[str] = None


# 仪表盘统计响应（一次请求返回首页要的全部数字/小列表）
class DashboardStats(BaseModel):
    inventory_count: int = 0          # 物料种类（全部，含禁用——与原前端口径一致）
    # 库存总量按赛道分组（斤 + 米 + 个 加不出有意义的数，不能给一个总数）
    stock_by_category: List[DashCategoryTotal] = []
    supplier_count: int = 0           # 供应商数（启用）
    category_count: int = 0           # 分类数（启用）
    warning_items: List[DashWarningItem] = []
    recent_records: List[DashRecentRecord] = []
    trend: List[DashTrendPoint] = []
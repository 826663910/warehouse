from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, func, CheckConstraint, Index, UniqueConstraint
from sqlalchemy.sql.sqltypes import TIMESTAMP, BigInteger, SmallInteger  # 导入数据库类型中的日期时间
from sqlalchemy.orm import relationship   # 导入关系映射
from .database import Base # 模型基类

# 用户表
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, nullable=False, comment='主键ID')
    username = Column(String(200), nullable=False, unique=True, comment='用户名称')
    password = Column(String(200), nullable=False, comment="用户密码")
    # role: 展示用（"管理员"/"普通用户"等），权限判断一律走 level。
    # 写入时由应用层根据 level 同步（level=1→user, 2→admin, 3→super_admin），不要直接改 role。
    role = Column(String(200), server_default='user', nullable=False, comment="用户角色（仅展示用，权限判断走 level）")
    level = Column(SmallInteger, server_default='1', nullable=False, comment='用户级别 1=普通 2=管理员 3=超级管理员（权限唯一来源）')
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("role in ('user', 'admin', 'super_admin')", name="role_check"),
    )

# 供应商表
class Supplier(Base):
    __tablename__='supplier'
    id = Column(Integer, primary_key=True, nullable=False, comment="主键ID")
    name = Column(String(200), nullable=False, unique=True, comment="供应商名称")
    contact = Column(String(50), comment="联系人")
    phone = Column(String(20), comment="联系电话")
    status = Column(SmallInteger, server_default="1", comment="状态 1启用 0禁用")
    sort_order = Column(Integer, server_default="0", comment="排序")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


# 类别表
class ProductCategory(Base):
    __tablename__ = "product_category"
    id = Column(Integer, primary_key=True, nullable=False, comment="主键ID")
    name = Column(String(50), nullable=False, comment="分类名称")
    parent_id = Column(BigInteger, nullable=False, server_default="0", comment="父分类ID (0=顶级分类)")
    level = Column(SmallInteger, nullable=False, server_default="1", comment="层级 (1/2/3...)")
    sort_order = Column(Integer, nullable=False, server_default="0", comment="排序值（越大越靠前）")
    # TINYINT(1) 在 SQLAlchemy 中用 SmallInteger 或 Booleannullable=False, 
    status = Column(SmallInteger,   server_default="1", comment="状态 (1启用 0禁用) ")

    # 定义索引（也可以写在 __table_args__ 中）
    __table_args__ = (
        Index("idx_parent", "parent_id"),
    )

# 客户表
class Customer(Base):
    __tablename__ = "customer"
    id = Column(Integer, primary_key=True, nullable=False, comment="主键ID")
    name = Column(String(200), nullable=False, unique=True, comment="客户名称")
    contact = Column(String(50), comment="联系人")
    phone = Column(String(20), comment="联系电话")
    status = Column(SmallInteger, server_default="1", comment="状态 1启用 0禁用")
    sort_order = Column(Integer, server_default="0", comment="排序")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

# 库存表
class Inventory(Base):
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True, nullable=False, comment="主键ID")
    mnemonic_code = Column(String(50), nullable=True, index=True, comment="助记码（拼音首字母）")
    code = Column(String(50), unique=True, nullable=False, index=True, comment="物料编码（如: 1001)")
    supplier_id = Column(Integer, ForeignKey('supplier.id', ondelete='CASCADE'), index=True, comment='所属供应商')
    category_id = Column(Integer, ForeignKey('product_category.id', ondelete='CASCADE'), index=True, comment='所属分类')
    root_category_id = Column(BigInteger, nullable=False, index=True, comment="所属一级分类ID(冗余)")
    name = Column(String(200), nullable=False, comment="物品名称")
    type = Column(String(200), comment='型号')
    stock = Column(Integer, nullable=False, comment='库存数量')
    unit_base = Column(String(50), comment='基础单位：库存实际存数用的最小单位(克/个/毫米)')
    unit_category = Column(String(20), server_default='count', comment='单位类型: weight/count/length/volume - 决定换算走哪条赛道')
    unit = Column(String(20), comment='基本计量单位：列表/详情默认显示用（如 公斤），必须同 category 内')
    warning = Column(Integer, nullable=True, comment='预警数量')
    avg_cost = Column(Numeric(10, 2), nullable=True, server_default='0', comment='移动加权平均成本')
    status = Column(SmallInteger,   server_default="1", comment="状态 (1启用 0禁用) ")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    packages = relationship('InventoryPackage', back_populates='inventory', 
                            cascade='all, delete-orphan')

    # 联合唯一索引
    __table_args__ = (
        UniqueConstraint('name', 'type', name='uq_name_type'),
    )

# 库存包装表
class InventoryPackage(Base):
    __tablename__ = 'inventory_package'
    id = Column(Integer, primary_key=True, index=True, nullable=False)
    inventory_id = Column(Integer, ForeignKey('inventory.id', ondelete='CASCADE'), nullable=False, index=True)
    unit_name = Column(String(20), nullable=False, comment='包装单位名（如 箱/袋/盒）')
    qty_per_base = Column(Integer, nullable=False, comment='1 包装 = 多少基础单位（如 1 箱=24 个，填 24)')
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    inventory = relationship('Inventory', back_populates='packages')
    # 联合唯一索引
    __table_args__ = (
        UniqueConstraint('inventory_id', 'unit_name', name='uq_inventory_id_unit_name'),
    )


# 单据主表
class StockOrder(Base):
    __tablename__ = "stock_orders"
    id = Column(BigInteger, primary_key=True, comment='主键')
    order_no = Column(String(50), unique=True, nullable=False, comment="入库/出库编号")
    order_type = Column(SmallInteger, nullable=False, comment="1入库 2出库 3退货 4报废")
    status = Column(SmallInteger, default=1, comment="1草稿 2已审 3作废")
    transaction_date = Column(TIMESTAMP(timezone=True), server_default=func.now(), comment="交易日期")
    supplier_id = Column(Integer, ForeignKey('supplier.id'), comment='供应商')
    customer_id = Column(Integer, ForeignKey('customer.id'), comment='客户')
    created_by = Column(String(50), comment="制单人")
    remark = Column(String(255), comment="备注")
    items = relationship("StockOrderDetail")
    created_at = Column(TIMESTAMP, server_default=func.now(), comment='创建时间')


# 单据明细表
class StockOrderDetail(Base):
    __tablename__ = "stock_order_details"
    id = Column(BigInteger, primary_key=True, comment='主键')
    order_id = Column(BigInteger, ForeignKey('stock_orders.id', ondelete='CASCADE'), comment='单据主表ID')
    inventory_id = Column(Integer, ForeignKey('inventory.id'), comment='库存ID')
    # 以下三个为冗余字段（历史快照）
    item_code = Column(String(50), comment='历史物料编码')
    item_name = Column(String(200), nullable=False, comment="历史物料名称")
    item_type = Column(String(200), comment='历史型号')
    item_unit = Column(String(20), comment='历史单位')
    # 核心数量
    quantity = Column(Integer, nullable=False, comment="数量（**基础单位**！所有数学运算走这个）")
    input_qty = Column(Numeric(10, 2), comment='用户录入的数量（按 input_unit 计）')
    input_unit = Column(String(20), comment='用户录入的单位（斤/公斤/个/...)')
    unit_price = Column(Numeric(10, 2), comment="单价")
    total_amount = Column(Numeric(10, 2), comment="总金额")  # 可存计算值
    line_remark = Column(String(255), comment="备注")

    __table_args__ = (
        Index("idx_order_id", "order_id"),
        Index("idx_inventory_id", "inventory_id")
    )

# 流水记录
class StockTransaction(Base):
    __tablename__ = "stock_transactions"
    id = Column(BigInteger, primary_key=True, comment='主键')
    inventory_id = Column(Integer, ForeignKey('inventory.id', ondelete='CASCADE'), comment='库存ID')
    order_id = Column(BigInteger, ForeignKey('stock_orders.id', ondelete='CASCADE'), comment='单据主表ID')
    order_type= Column(SmallInteger, nullable=False, comment="单据类型 1入库 2出库 3退货 4报废")
    transaction_date = Column(TIMESTAMP(timezone=True), server_default=func.now(), comment="记录日期")
    before_quantity = Column(Integer, nullable=False, comment="交易前数量")
    change_quantity = Column(Integer, nullable=False, comment='更改的数量')
    after_quantity = Column(Integer, nullable=False, comment='交易后数量')
    unit_cost = Column(Numeric(12, 2), comment='该笔流水的单位成本快照')
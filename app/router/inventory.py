from fastapi import APIRouter, status, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession  # 异步会话注解
from sqlalchemy import select, exists, or_, func   # 查询
from ..database import get_db  # 会话工厂
from .. import model, schemas, oauth2   # 模型和架构
from typing import Annotated, List, Optional
from pypinyin import lazy_pinyin, Style

router = APIRouter(
    prefix='/inventory',
    tags=['INVENTORY']
)

def generate_mnemonic(text: str) -> str:
    """将中文转换为拼音首字母（如：减速机 -> JSJ)"""
    if not text:
        return ""
    # 提取每个汉字的首字母
    pinyins = lazy_pinyin(text, style=Style.FIRST_LETTER)
    return ''.join(pinyins).upper()

# 允许排序的字段白名单（键=前端传的字段名，值=数据库列），防止 SQL 注入
SORTABLE_FIELDS = {
    'id': model.Inventory.id,
    'code': model.Inventory.code,
    'name': model.Inventory.name,
    'type': model.Inventory.type,
    'stock': model.Inventory.stock,
    'warning': model.Inventory.warning,
}


@router.get('/', response_model=schemas.InventoryPage)
async def get_inventory(db: Annotated[AsyncSession, '数据库会话', Depends(get_db)], 
                        user: Annotated[int, '用户', Depends(oauth2.require_user)],
                        name: Optional[str] = None, type: Optional[str] = None, 
                        limit: int = 10, offset: int = 0,
                        sort_by: Optional[str] = None, order: Optional[str] = 'asc',
                        status: Optional[int] = None,
                        supplier_id: Optional[int] = None,
                        category_id: Optional[int] = None):

    # 过滤条件列表
    # status 筛选：None 默认只看启用（与旧版行为一致）；-1 全部；0 只看禁用；1 只看启用
    # 注意不能写成 `Inventory.status == status`——status=None 时会生成 `WHERE status = NULL`，一行都查不到
    if status is None:
        conditions = [model.Inventory.status == 1]
    elif status == -1:
        conditions = []
    else:
        # 非法值（不是 0/1）按启用兜底，避免意外查全
        conditions = [model.Inventory.status == (status if status in (0, 1) else 1)]

    # 2. 过滤条件
    if name:          # 名称 / 助记码 / 物料编码，任意命中即可
        conditions.append(or_(
            model.Inventory.name.contains(name),
            model.Inventory.mnemonic_code.contains(name),
            model.Inventory.code.contains(name),
        ))
    if type:
        conditions.append(model.Inventory.type.contains(type))
    # 供应商维度：供应商页跳转过来时用，None / 0 都视作不过滤
    if supplier_id:
        conditions.append(model.Inventory.supplier_id == supplier_id)
    # 分类维度：分类页跳转过来时用；只筛出挂在这个分类下的物料（非末级分类本身没物料，给出 0 让其退化为不过滤）
    if category_id:
        conditions.append(model.Inventory.category_id == category_id)

    # 3. 查询总数（分页/排序参数不能进 count，否则 total 会变成每页条数）
    count_stmt = select(func.count(model.Inventory.id)).where(*conditions)
    total = await db.scalar(count_stmt)

    # 4. 排序字段走白名单，非法值回退到 id
    sort_col = SORTABLE_FIELDS.get(sort_by or '', model.Inventory.id)
    order_clause = sort_col.desc() if (order or '').lower() == 'desc' else sort_col.asc()

    # 5. 查询语句（第二排序键固定 id，保证翻页顺序稳定）
    stmt = (select(model.Inventory)
            .where(*conditions)
            .order_by(order_clause, model.Inventory.id)
            .limit(limit).offset(offset))
    result = await db.execute(stmt)     # 执行sql
    inventory = result.scalars().all()  # 返回所有

    # 6. 拼装展示用字段：分类路径（"一级/末级"）和供应商名。
    # 不用 N+1：只 in_ 查一次相关分类和供应商，本地在内存里 join。
    # root_category_id 也是 ProductCategory.id，所以一次 in_ 查询同时覆盖了"末级"和"一级"。
    """使用set推导式, 以合集的方式, 拿到inv的外键category_id和root_category_id"""
    category_ids = {inv.category_id for inv in inventory if inv.category_id} | {
        inv.root_category_id for inv in inventory if inv.root_category_id
    }
    """使用set推导式, 拿到inv的外键supplier_id"""
    supplier_ids = {inv.supplier_id for inv in inventory if inv.supplier_id}
    category_map = {}   # 分类映射表（id -> 分类）
    # 当category_ids不为空时，用in的方式查询所有分类
    if category_ids:
        rows = await db.scalars(
            select(model.ProductCategory).where(model.ProductCategory.id.in_(category_ids))
        )
        # 使用字典推导式, 建立分类id与分类实例的映射
        category_map = {c.id: c for c in rows}
    supplier_map = {}
    # 当supplier_ids不为空时，用in的方式查询所有供应商
    if supplier_ids:
        rows = await db.scalars(
            select(model.Supplier).where(model.Supplier.id.in_(supplier_ids))
        )
        # 使用字典推导式, 建立供应商id与供应商实例的映射
        supplier_map = {s.id: s for s in rows}

    # 循环遍历所有库存，根据分类映射表和供应商映射表，拼装分类路径和供应商名
    for inv in inventory:
        leaf = category_map.get(inv.category_id)    # 查映射
        root = category_map.get(inv.root_category_id)
        if leaf and root and root.id != leaf.id:
            inv.category_path = f"{root.name}/{leaf.name}"
        elif leaf:
            # 一级分类就是末级（没有二级/三级），不重复显示
            inv.category_path = leaf.name
        sup = supplier_map.get(inv.supplier_id)  # 查映射
        inv.supplier_name = sup.name if sup else None

    return {"total": total, "items": inventory}

@router.get('/{id}')
async def get_inventory_id(id: int, db: Annotated[AsyncSession, '数据库会话', Depends(get_db)],
                           user: Annotated[int, '用户', Depends(oauth2.require_user)]):
    stmt = select(model.Inventory).where(model.Inventory.id==id)
    result = await db.execute(stmt)
    inventory = result.scalar_one_or_none()
    if not inventory:
        raise HTTPException(status_code=404, detail="没有这个库存!")
    return inventory


# 自动生成物料编码
async def generate_item_code(db: AsyncSession) -> str:
    # 查当前最大的 code（假设 code 是纯数字字符串）
    stmt = select(func.max(model.Inventory.code)).where(model.Inventory.code != "")
    result = await db.scalar(stmt)
    if result:
        return str(int(result) + 1).zfill(4)  # 补全4位，1001, 1002...
    return "1001"


@router.post('/')
async def create_inventory(inventory: schemas.InventoryCreate, db: Annotated[AsyncSession, '数据库会话', Depends(get_db)],
                       user: Annotated[int, '用户', Depends(oauth2.require_user)]):
    # 检查分类是否存在
    category = await db.get(model.ProductCategory, inventory.category_id)
    if not category:
        raise HTTPException(status_code=400, detail="分类不存在!")

    # 用exists检查是否有子集
    stmt = select(exists().where(model.ProductCategory.parent_id==inventory.category_id))
    has_child = await db.scalar(stmt)   # 返回true或false
    if has_child:
        raise HTTPException(status_code=400, detail=f"分类 '{category.name}' 非末级，不能挂载物品")

    # 查询父级
    current = category
    while current.parent_id != 0:
        current = await db.get(model.ProductCategory, current.parent_id)
        if not current:
            break
    root_id = current.id if current else category.id

    # 判断生成助记码
    if not inventory.mnemonic_code:
        mnemonic = generate_mnemonic(inventory.name)

    else:
        mnemonic = inventory.mnemonic_code.upper()

    # 调用生成物料编码
    code = await generate_item_code(db)

    # 插入数据
    inventory = model.Inventory(**inventory.model_dump(exclude={'mnemonic_code', 'code'}), 
                                root_category_id=root_id, mnemonic_code=mnemonic, code=code)
    db.add(inventory)
    await db.commit()
    await db.refresh(inventory)
    return inventory


@router.patch('/{id}')
async def update_inventory(id: int, inventory_update: schemas.InventoryUpdate, db: Annotated[AsyncSession, '数据库会话', Depends(get_db)],
                       user: Annotated[int, '用户', Depends(oauth2.require_user)]):
    # 1.查出现有物品
    inv = await db.get(model.Inventory, id)
    if not inv:
        raise HTTPException(status_code=404, detail="没有这个库存!")

    # 2. 取出前端传入的字段
    update_data = inventory_update.model_dump(exclude_unset=True)

    # 2.1 如果更新了状态，校验只能是 0（禁用）/ 1（启用）
    if 'status' in update_data and update_data['status'] not in (0, 1):
        raise HTTPException(status_code=400, detail="status 只能为 0（禁用）或 1（启用）")

    # 3. ⭐ 核心逻辑：如果更新了分类
    if 'category_id' in update_data:
        new_category_id = update_data['category_id']
        
        # 3.1 验证分类是否存在
        category = await db.get(model.ProductCategory, new_category_id)
        if not category:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分类不存在")
        
        # 3.2 验证新分类是否为末级（不能挂在文件夹上）
        has_child_stmt = select(exists().where(model.ProductCategory.parent_id == new_category_id))
        has_child = await db.scalar(has_child_stmt)
        if has_child:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"分类 '{category.name}' 非末级，不能挂载物品")
        
        # 3.3 根据新分类，重算 root_category_id（复用你之前的 While 循环逻辑）
        current = category
        while current.parent_id != 0:
            current = await db.get(model.ProductCategory, current.parent_id)
            if not current:
                break
        root_id = current.id if current else category.id
        
        # 3.4 赋值
        inv.category_id = new_category_id
        inv.root_category_id = root_id
        
        # 防止后面 setattr 重复赋 category_id
        update_data.pop('category_id')

    # 4. 更新其他普通字段（name, stock, supplier_id 等）
    for key, value in update_data.items():
        setattr(inv, key, value)

    await db.commit()
    await db.refresh(inv)
    return inv

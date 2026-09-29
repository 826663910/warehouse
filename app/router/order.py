from fastapi import APIRouter, status, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession  # 异步会话注解
from sqlalchemy import select, exists, or_, func, update   # 查询
from sqlalchemy.orm import selectinload # where .... in
from sqlalchemy.exc import SQLAlchemyError
from ..database import get_db  # 会话工厂
from .. import model, schemas, oauth2   # 模型和架构
from typing import Annotated, List, Optional
from datetime import datetime, timezone
import pytz   # pip install pytz
import random

router = APIRouter(
    prefix='/order',
    tags=['ORDER']
)


# 单据列表页
@router.get('/', response_model=schemas.OrderListPage)
async def get_list_order(db: Annotated[AsyncSession, Depends(get_db)],
                         current_user_id: Annotated[int, Depends(oauth2.require_user)],
                         order_no: Optional[str] = None, order_type: Optional[int] = None,
                         start_day: Optional[str] = None, end_day: Optional[str] = None,
                         status: Optional[int] = None,
                         limit: int = 10, offset: int = 0):
    # 过滤条件(空列表)
    conditions = []
    
    # 过滤单据号
    if order_no:
        conditions.append(model.StockOrder.order_no.contains(order_no))  # 放入列表

    # 过滤单据类型（用 is not None，避免 0 值被当成"没传"）
    if order_type is not None:
        conditions.append(model.StockOrder.order_type==order_type)

    # 过滤单据状态（同理，将来若出现 status=0 也能正确过滤）
    if status is not None:
        conditions.append(model.StockOrder.status==status)
    
    # 过滤开始结束时间
    if start_day and end_day:
        # 将str解析为datetime.date()
        start_date = datetime.strptime(start_day, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_day, '%Y-%m-%d').date()
        # localize: 加时区, 把naive时间变为加8小时的aware时间   astimezone: 转换为UTC时间
        shanghai_tz = pytz.timezone('Asia/Shanghai')
        start_utc = shanghai_tz.localize(datetime.combine(start_date, datetime.min.time())).astimezone(pytz.UTC)
        end_utc = shanghai_tz.localize(datetime.combine(end_date, datetime.max.time())).astimezone(pytz.UTC)
        # between: 在两个时间之间
        conditions.append(model.StockOrder.transaction_date.between(start_utc, end_utc)) # 放入列表

    # 查询总数（count 查询不能带 order_by / limit / offset）
    count_stmt = select(func.count(model.StockOrder.id)).where(*conditions)
    total = await db.scalar(count_stmt)
    
    # 查询结果
    stmt = (select(model.StockOrder)
            .where(*conditions)
            .order_by(model.StockOrder.transaction_date.desc())
            .limit(limit)
            .offset(offset))
    result = await db.execute(stmt) # 执行查询
    orders = result.scalars().all()   # 返回所有结果

    return {"total": total, "items": orders}


# 单据详情页
@router.get('/{order_id}', response_model=schemas.OrderOut)
async def get_order(order_id: int, db: Annotated[AsyncSession, Depends(get_db)],
                     current_user_id: Annotated[int, Depends(oauth2.require_user)]):
    # 查询订单列表
    stmt = select(model.StockOrder).where(model.StockOrder.id==order_id).options(selectinload(model.StockOrder.items))
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='该单据不存在!')
    return order


# 库存搜索接口
@router.get('/inventory/search', response_model=List[schemas.OrderSearchInventory])
async def search_inventory(db: Annotated[AsyncSession, Depends(get_db)],
                           current_user_id: Annotated[int, Depends(oauth2.require_user)],
                           name: Optional[str] = None, type: Optional[str] = None,
                           limit: int = 10):
    # 过滤条件
    conditions = [model.Inventory.status == 1]

    # TODO: 如果将来库存超过 10 万条导致搜索变慢，考虑改成 startswith 或接入全文检索
    # name 同时糊配 名称/助记码/编码/型号：前端单框输入一个词时，不必区分搜的是名称还是型号
    if name:
        conditions.append(or_(model.Inventory.mnemonic_code.contains(name), model.Inventory.name.contains(name),
                              model.Inventory.code.contains(name), model.Inventory.type.contains(name)))
    # type 是「名称 型号」两段输入时的第二段，与 name 是 AND 关系
    if type:
        conditions.append(model.Inventory.type.contains(type))

    # 搜索库存
    stmt = select(model.Inventory).where(*conditions).limit(limit)
    result = await db.execute(stmt)
    inventories = result.scalars().all()
    return inventories


# 生成单据号
def generate_order_no(order_type: int):
    if order_type == 1:
        return 'IN' + datetime.now().strftime('%Y%m%d%H%M%S') + str(random.randint(1000, 9999))
    elif order_type == 2:
        return 'OUT' + datetime.now().strftime('%Y%m%d%H%M%S') + str(random.randint(1000, 9999))
    elif order_type == 3:
        return 'RET' + datetime.now().strftime('%Y%m%d%H%M%S') + str(random.randint(1000, 9999))
    elif order_type == 4:
        return 'SCR' + datetime.now().strftime('%Y%m%d%H%M%S') + str(random.randint(1000, 9999))
    else:
        raise HTTPException(status_code=400, detail="无效的订单类型")


# 插入主表和明细表的数据(草稿)
@router.post('/')
async def create_order(order: schemas.OrderCreate,
                       db: Annotated[AsyncSession, '数据库会话', Depends(get_db)], 
                       current_user_id: Annotated[int, '用户', Depends(oauth2.require_user)],):
    # 查询用户名
    user = await db.get(model.User, current_user_id.id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有这个用户!")

    # 判断查询供应商
    if order.order_type == 1 and order.supplier_id:
        supplier = await db.get(model.Supplier, order.supplier_id)
        if not supplier:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有这个供应商!")

    # 插入主表
    new_order = model.StockOrder(
        order_no = generate_order_no(order.order_type),
        order_type = order.order_type,
        supplier_id = order.supplier_id,
        transaction_date = datetime.now(),
        created_by = user.username,
        remark = order.remark,
        status = 1
    )
    db.add(new_order)
    await db.flush()    # 获取new_order的id

    # 循环插入明细表
    for item in order.items:
        inventory = await db.get(model.Inventory, item.inventory_id)
        if not inventory:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有这个库存!")
        if inventory.status != 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该物品已禁止, 无法出入库!")

        # 计算总价（数量x单价）
        price = item.price if item.price is not None else 0.0
        total_amount = item.quantity * price

        # 插入明细表
        new_item = model.StockOrderDetail(
            order_id = new_order.id,
            item_code = inventory.code,
            item_name = inventory.name,
            item_type = inventory.type,
            item_unit = inventory.unit,
            inventory_id = item.inventory_id,
            quantity = item.quantity,
            unit_price = price,
            total_amount = total_amount,
            line_remark = item.line_remark
        )
        db.add(new_item)    # 添加
    await db.commit()       # 提交
    await db.refresh(new_order, attribute_names=['items'])  # 刷新
    return new_order


# 审核主表和明细表
@router.post('/review/{order_id}')
async def review_order(order_id: int, 
                       db: Annotated[AsyncSession, '数据库会话', Depends(get_db)], 
                       current_user_id: Annotated[int, '用户', Depends(oauth2.require_user)]):
    # 查单据
    stmt = select(model.StockOrder).where(model.StockOrder.id==order_id).options(selectinload(model.StockOrder.items))
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有这个单据!")

    if order.status != 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='只有草稿状态下的单据, 才能审核!')

    try:
        # 4.1 修改主表状态
        order.status = 2  # 假设 2 = 已审核

        # 4.2 如果是入库单，循环增加每个物料的库存
        if order.order_type == 1:
            for item in order.items:
                # 入库时检查物料是否存在
                inventory = await db.get(model.Inventory, item.inventory_id)
                if not inventory:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有这个库存!")
                # 放入变量和事务隔开
                before_qty = inventory.stock
                
                # 原子更新：库存 + 需求量
                update_result = await db.execute(
                    update(model.Inventory)
                    .where(model.Inventory.id == item.inventory_id)
                    .values(stock=model.Inventory.stock + item.quantity)
                )

                # 如果影响行数为0，说明物料不存在
                if update_result.rowcount == 0:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                                        detail=f"入库失败, 物料ID {item.inventory_id} 对应的库存记录不存在")

                await db.refresh(inventory) # 刷新

                # 添加入库流水
                db.add(model.StockTransaction(
                    inventory_id = item.inventory_id,
                    order_id = item.order_id,
                    order_type = order.order_type,
                    transaction_date = datetime.now(),
                    before_quantity = before_qty,
                    change_quantity = item.quantity,
                    after_quantity = inventory.stock,
                ))

        # 4.3 如果是出库单，退货单, 报废单循环扣减每个物料的库存
        elif order.order_type in (2, 3, 4):
            for item in order.items:
                # 出库时检查库存和物料
                inventory = await db.get(model.Inventory, item.inventory_id)
                if not inventory:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有这个库存!")
                if inventory.stock < item.quantity:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="库存不足!")
                # 放入变量和事务隔开
                before_qty = inventory.stock

                # 原子更新：只有库存 >= 需求量时才扣减，防止并发超卖
                update_result = await db.execute(
                    update(model.Inventory)
                    .where(
                        model.Inventory.id == item.inventory_id,
                        model.Inventory.stock >= item.quantity  # 关键条件
                    )
                    .values(stock=model.Inventory.stock - item.quantity)
                )
                # 如果 affected_rows == 0，说明库存不够或被其他事务抢先扣了
                if update_result.rowcount == 0:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                                        detail=f"物料 {item.item_name} 库存不足或已被占用，请刷新后重试")
                await db.refresh(inventory) # 刷新

                # 添加出库流水
                db.add(model.StockTransaction(
                    inventory_id = item.inventory_id,
                    order_id = item.order_id,
                    order_type = order.order_type,
                    transaction_date = datetime.now(),
                    before_quantity = before_qty,
                    change_quantity = -item.quantity,
                    after_quantity = inventory.stock,
                ))

                
        # 4.4如果是其他没有的类型, 则拦截
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的订单类型")

        await db.commit()   # 提交事务

    except SQLAlchemyError:
        # 如果发生任何异常，事务会自动回滚（因为 SQLAlchemy 会在异常时 rollback）
        await db.rollback()
        raise  # 重新抛出异常，让 FastAPI 返回错误给前端

    # 5. 刷新订单对象（获取最新的数据库状态，但此时 items 因为 selectinload 已存在，直接返回即可）
    await db.refresh(order, attribute_names=['items'])
    return order  # 返回审核后的完整订单

    
# 更新主表, 删旧插新明细表
@router.patch('/{order_id}')
async def update_order(order_id: int, order_update: schemas.OrderUpdate,
                      db: Annotated[AsyncSession, '数据库会话', Depends(get_db)], 
                      current_user_id: Annotated[int, '用户', Depends(oauth2.require_user)]):
    # 1.验证用户
    user = await db.get(model.User, current_user_id.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='用户不存在!')

    # 2. 查询现有订单（带明细，为了后续替换）
    stmt = select(model.StockOrder).where(model.StockOrder.id==order_id).options(selectinload(model.StockOrder.items))
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='订单不存在!')

    # 3. 状态校验：只有草稿（status=1）可修改
    if order.status != 1:
        raise HTTPException(status_code=400, detail="只有草稿状态的订单才能修改")

    # 4. 若更新了供应商，校验供应商是否存在
    if order_update.supplier_id is not None and order_update.supplier_id != order.supplier_id:
        supplier = await db.get(model.Supplier, order_update.supplier_id)
        if not supplier:
            raise HTTPException(status_code=404, detail="供应商不存在")

    # 5. 更新主表字段（只更新传入的非 None 字段）
    update_data = order_update.model_dump(exclude_unset=True)  # 只取前端传了的字段

    # 如果更新了单据类型，则生成新的单据号
    if 'order_type' in update_data:
        update_data['order_no'] = generate_order_no(update_data['order_type'])

    # 更新主表字段
    for key, value in update_data.items():
        if key == 'items':   # 明细单独处理
            continue
        setattr(order, key, value)

    # 6. 删除旧明细表
    for item in order.items:
        await db.delete(item)
    
    # 7. 插入新明细表
    if order_update.items:
        for item in order_update.items:
            # TODO: 处理新明细项
            # 校验库存
            inventory = await db.get(model.Inventory, item.inventory_id)
            if not inventory:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"库存ID {item.inventory_id} 不存在")
            if inventory.status != 1:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"物品 {inventory.name} 已禁用")

            price = item.price if item.price is not None else 0.0
            total_amount = item.quantity * price

            new_item = model.StockOrderDetail(
                order_id=order.id,
                item_code=inventory.code,
                item_name=inventory.name,
                item_type=inventory.type,
                item_unit=inventory.unit,
                inventory_id=item.inventory_id,
                quantity=item.quantity,
                unit_price=price,
                total_amount=total_amount,
                line_remark=item.line_remark
            )
            db.add(new_item)
    
    await db.commit()   # 提交
    await db.refresh(order, attribute_names=['items'])  # 刷新
    return order   # 返回更新后的单据


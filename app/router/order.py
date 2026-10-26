from fastapi import APIRouter, status, HTTPException, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession  # 异步会话注解
from sqlalchemy import select, exists, or_, func, update   # 查询
from sqlalchemy.orm import selectinload # where .... in
from ..database import get_db  # 会话工厂
from .. import model, schemas, oauth2, unit_convert_tool   # 模型和架构
from typing import Annotated, List, Optional
from datetime import datetime, timezone
import pytz   # pip install pytz
import random

router = APIRouter(
    prefix='/order',
    tags=['ORDER']
)


def _resolve_quantity(inventory, input_qty, input_unit, legacy_quantity=None, packages=()):
    """把用户录入的（数量 + 单位）换算成【基础单位整数】，并校验单位合法性。

    返回 (input_qty, input_unit, quantity_base):
      - input_qty / input_unit: 用户原始录入，用于审计与展示（"5 斤")
      - quantity_base: 基础单位整数(2500 克），库存加减、成本运算只认这个

    packages = 该物料的包装规格（大小件）。录入"3 箱"时按包装乘数换算成 72 个。
    调用方负责查出来传进来 (async 下 relationship 不能属性访问）。

    【兼容旧前端】只传了 quantity 时，视作已是基础单位，原样使用（等前端改完可删该分支）。
    """
    # 兼容分支：旧前端直接给基础单位数量
    if input_qty is None and legacy_quantity is not None:
        if int(legacy_quantity) <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"'{inventory.name}' 的数量必须大于 0")
        return float(legacy_quantity), (input_unit or inventory.unit), int(legacy_quantity)

    if input_qty is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"'{inventory.name}' 缺少数量（input_qty 或 quantity）")

    # 无赛道（老数据 unit_category 为 NULL）按 count 处理：无换算表，原样存取
    category = inventory.unit_category or 'count'
    unit = input_unit or inventory.unit
    qty = float(input_qty)

    # 安全墙：单位必须属于该物料的赛道【或】是它自己的包装单位，
    # 禁止「斤」配「count」这类跨类组合。包装是物料私有的，不在全局表里，要单独放行。
    supported = unit_convert_tool.get_supported_units(category)
    pkg_names = [p.unit_name for p in packages]
    if supported and unit not in supported and unit not in pkg_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"单位 '{unit}' 不属于 '{inventory.name}' 的单位类型 '{category}'，可选: {supported + pkg_names}"
        )

    base = unit_convert_tool.to_base(qty, unit, category, packages)
    if base <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"'{inventory.name}' 的数量必须大于 0")
    return qty, unit, base


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

    # 逐行把【基础单位】数量换算成【物料显示单位】的展示值。
    # 注意：必须遍历全部明细——只算 items[0] 的话，第 2 行往后 quantity_display 全是 None。
    for item in order.items:
        inv = await db.get(model.Inventory, item.inventory_id)
        if inv is None:
            continue   # 物料已被删除的旧单据，跳过换算，前端会用 quantity 兜底
        item.quantity_display = unit_convert_tool.from_base(item.quantity, inv.unit, inv.unit_category)

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

    # 搜索库存。带 packages：开单时要能按包装单位（箱/盒）录入
    # （有 response_model=List[OrderSearchInventory]，Pydantic 只输出声明字段，不会递归）
    stmt = (select(model.Inventory).where(*conditions)
            .options(selectinload(model.Inventory.packages))
            .limit(limit))
    result = await db.execute(stmt)
    inventory = list(result.scalars().all())
    for inv in inventory:
        inv.stock_display = unit_convert_tool.from_base(inv.stock, inv.unit, inv.unit_category)
    return inventory


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

    # 入库时判断查询供应商
    if order.order_type == 1 and order.supplier_id:
        supplier = await db.get(model.Supplier, order.supplier_id)
        if not supplier:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有这个供应商!")

    # 出库时判断查询客户
    if order.order_type == 2 and order.customer_id:
        customer = await db.get(model.Customer, order.customer_id)
        if not customer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有这个客户!")

    # 退货是判断查询功能供应商
    if order.order_type == 3 and order.supplier_id:
        supplier = await db.get(model.Supplier, order.supplier_id)
        if not supplier:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有这个供应商!")

    # 插入主表
    new_order = model.StockOrder(
        order_no = generate_order_no(order.order_type),
        order_type = order.order_type,
        supplier_id = order.supplier_id,
        customer_id = order.customer_id,
        # 业务日期用前端选的；没传才兜底"此刻"
        # （和 update_order 保持同一口径：表单里选的日期就是 transaction_date）
        transaction_date = order.transaction_date or datetime.now(),
        created_by = user.username,
        remark = order.remark,
        status = 1
    )
    db.add(new_order)
    await db.flush()    # 获取new_order的id

    # 循环插入明细表
    for item in order.items:
        # options 里 selectinload：一次性把包装规格（大小件）也查出来。
        # async 下不能懒加载 relationship（会抛 MissingGreenlet），而 awaitable_attrs
        # 需要 Base 继承 AsyncAttrs ——本项目 Base 是 declarative_base()，没有这个属性。
        inventory = await db.get(
            model.Inventory, item.inventory_id,
            options=[selectinload(model.Inventory.packages)]
        )
        if not inventory:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有这个库存!")
        if inventory.status != 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该物品已禁止, 无法出入库!")

        # 已被 selectinload 预加载，可直接读
        packages = inventory.packages

        # 单价语义随单据类型变：入库=采购价、出库=售价、退货=退货价
        # 报废单没有"成交价"：单价改存"当时的库存均价"，total_amount 即"报废损失"，详情页直接展示
        if order.order_type == 4:
            price = (inventory.avg_cost or 0)
        else:
            price = item.price if item.price is not None else 0.0

        # 单位换算：用户录入的（数量 + 单位）→ 基础单位整数
        input_qty, input_unit, quantity = _resolve_quantity(
            inventory, item.input_qty, item.input_unit, item.quantity, packages)
        # 金额 = 换算成【物料显示单位】的数量 × 单价。
        #   单价锚定在物料的显示单位上（螺丝按斤报价），开单单位只是临时称量方式。
        #   所以"20 公斤"要按 40 斤计价 → 换更大的单位，钱跟着变多，符合直觉。
        # 报废单例外：它的"单价"是库存均价（每基础单位），只能 base × base。
        total_amount = unit_convert_tool.from_base(quantity, inventory.unit, inventory.unit_category) * price

        # 插入明细表
        new_item = model.StockOrderDetail(
            order_id = new_order.id,
            item_code = inventory.code,
            item_name = inventory.name,
            item_type = inventory.type,
            item_unit = inventory.unit,
            inventory_id = item.inventory_id,
            quantity = quantity,        # 基础单位：库存加减、成本运算只认这个
            input_qty = input_qty,      # 用户录入：审计 + 展示（"5 斤"）
            input_unit = input_unit,
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
                       current_user_id: Annotated[int, '用户', Depends(oauth2.require_role)]):
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
            # 按 inventory_id 升序加锁：多张单据并发审核时，若明细顺序相反（A 锁5再锁3，B 锁3再锁5）会触发死锁
            # 统一顺序后，每张单据都是"从低 id 到高 id"逐行加锁，MySQL 不会再回滚任何一边
            for item in sorted(order.items, key=lambda x: x.inventory_id):
                # 入库时检查物料是否存在
                inventory = (await db.execute(
                    select(model.Inventory)
                    .where(model.Inventory.id == item.inventory_id)
                    .with_for_update()      # 行锁
                )).scalar_one_or_none()     # 返回第一行
                if not inventory:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有这个库存!")
                
                # 放入变量和事务隔开
                before_qty = inventory.stock

                # 计算移动加权平均成本, 这里的价格
                # 总成本 = 旧成本 + 新成本
                # ⚠️ 用 total_amount（真实花的钱），不能用 quantity × unit_price：
                #    unit_price 是「每录入单位」的价，quantity 是基础单位，跨单位相乘会放大几十~几百倍。
                #    录入单位 = 基础单位时两者结果相同，所以此改动向后兼容。
                total_cost = (unit_convert_tool.from_base(inventory.stock, inventory.unit, inventory.unit_category)) * (inventory.avg_cost or 0) + (item.total_amount or 0)
                inventory.stock += item.quantity    # 库存增加(最小单位数量)
                inventory.avg_cost = total_cost / (unit_convert_tool.from_base(inventory.stock, inventory.unit, inventory.unit_category))   # 平均成本

                # 添加入库流水
                db.add(model.StockTransaction(
                    inventory_id = item.inventory_id,
                    order_id = item.order_id,
                    order_type = order.order_type,
                    transaction_date = order.transaction_date or datetime.now(),
                    before_quantity = before_qty,
                    change_quantity = item.quantity,
                    after_quantity = inventory.stock,
                    unit_cost = item.unit_price
                ))

        # 4.3 如果是出库单，退货单, 报废单循环扣减每个物料的库存
        elif order.order_type in (2, 3, 4):
            # 同样按 inventory_id 升序加锁：详见上面入库分支的注释
            for item in sorted(order.items, key=lambda x: x.inventory_id):
                # 出库时检查库存和物料
                inventory = (await db.execute(
                    select(model.Inventory)
                    .where(model.Inventory.id == item.inventory_id)
                    .with_for_update()        # 行锁
                    )).scalar_one_or_none()   # 返回第一行
                if not inventory:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有这个库存!")
                if inventory.stock < item.quantity:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="库存不足!")
                # 放入变量和事务隔开
                before_qty = inventory.stock
                cost_snapshot = inventory.avg_cost or 0

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


                # 报废单：把【审核这一刻】的实际成本快照回写到明细，
                # 保证单据详情页的"报废损失" = 真实结转成本（草稿期存的是预估均价，可能已变）
                if order.order_type == 4:
                    item.unit_price = cost_snapshot
                    item.total_amount = unit_convert_tool.from_base(item.quantity, inventory.unit, inventory.unit_category) * cost_snapshot

                # 添加出库流水
                db.add(model.StockTransaction(
                    inventory_id = item.inventory_id,
                    order_id = item.order_id,
                    order_type = order.order_type,
                    transaction_date = order.transaction_date or datetime.now(),
                    before_quantity = before_qty,
                    change_quantity = -item.quantity,
                    after_quantity = before_qty - item.quantity,
                    unit_cost = cost_snapshot
                ))

                
        # 4.4如果是其他没有的类型, 则拦截
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的订单类型")

        await db.commit()   # 提交事务

    except Exception:
        # 任何异常都走这里：HTTPException（库存不足 / 物料不存在等业务异常）走这里 rollback 后抛给 FastAPI 转 4xx；
        # SQLAlchemyError / 网络异常等也走这里 → 5xx。get_db 退出时即使不显式 rollback 也会回滚，这里写出来更清楚。
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

    # 若更新了客户, 校验客户是否存在
    if order_update.customer_id is not None and order_update.customer_id != order.customer_id:
        customer = await db.get(model.Customer, order_update.customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="客户不存在")

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
            # 同 create_order：selectinload 预加载包装规格，async 下才能直接读
            inventory = await db.get(
                model.Inventory, item.inventory_id,
                options=[selectinload(model.Inventory.packages)]
            )
            if not inventory:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"库存ID {item.inventory_id} 不存在")
            if inventory.status != 1:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"物品 {inventory.name} 已禁用")

            packages = inventory.packages

            # 同 create_order：报废单的"单价"存库存均价，total_amount 即报废损失
            if order.order_type == 4:
                price = (inventory.avg_cost or 0)
            else:
                price = item.price if item.price is not None else 0.0

            # 同 create_order：录入数量 + 单位 → 基础单位数量
            input_qty, input_unit, quantity = _resolve_quantity(
                inventory, item.input_qty, item.input_unit, item.quantity, packages)
            # 同 create_order：金额按【物料显示单位】计价；报废单是 base × base
            total_amount = unit_convert_tool.from_base(quantity, inventory.unit, inventory.unit_category) * price

            new_item = model.StockOrderDetail(
                order_id=order.id,
                item_code=inventory.code,
                item_name=inventory.name,
                item_type=inventory.type,
                item_unit=inventory.unit,
                inventory_id=item.inventory_id,
                quantity=quantity,
                input_qty=input_qty,
                input_unit=input_unit,
                unit_price=price,
                total_amount=total_amount,
                line_remark=item.line_remark
            )
            db.add(new_item)
    
    await db.commit()   # 提交
    await db.refresh(order, attribute_names=['items'])  # 刷新
    return order   # 返回更新后的单据

@router.delete('/{order_id}')
async def delete_order(order_id: int, 
                       db: Annotated[AsyncSession, '数据库会话', Depends(get_db)], 
                       current_user_id: Annotated[int, '用户', Depends(oauth2.require_role)]):
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
    
    # 3. 状态校验：只有草稿（status=1）可删除
    if order.status != 1:
        raise HTTPException(status_code=400, detail="只有草稿状态的订单才能删除")
    
    # 4. 删除主表
    await db.delete(order)
    
    # 5. 删除明细表
    for item in order.items:
        await db.delete(item)
    
    await db.commit()   # 提交
    return Response(status_code=status.HTTP_204_NO_CONTENT)
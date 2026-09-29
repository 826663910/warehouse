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

router = APIRouter(
    prefix='/record',
    tags=['RECORD']
)

# 查询记录
@router.get('/', response_model=schemas.RecordPage)
async def get_record(db: Annotated[AsyncSession, Depends(get_db)],
                     user: Annotated[int, '用户', Depends(oauth2.require_user)],
                     start_day: Optional[str] = None, end_day: Optional[str] = None,
                     keyword: Optional[str] = None, direction: Optional[int] = None,
                     limit: int = 10, offset: int = 0):
    """查询出入库流水
    start_day/end_day: 日期范围, 格式 YYYY-MM-DD, 需成对传入
    keyword: 物料名称 / 型号 模糊搜索
    direction: 1=入库(数量增加) 2=出库(数量减少)
    返回: {"total": 总条数, "items": [流水记录, ...]}
    """
    # 1. 公共过滤条件
    conditions = [model.Inventory.status == 1]

    # 日期范围
    if start_day and end_day:
        # 将str解析为datetime.date()
        start_date = datetime.strptime(start_day, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_day, '%Y-%m-%d').date()
        # localize: 加时区, 把naive时间变为加8小时的aware时间   astimezone: 转换为UTC时间
        shanghai_tz = pytz.timezone('Asia/Shanghai')
        start_utc = shanghai_tz.localize(datetime.combine(start_date, datetime.min.time())).astimezone(pytz.UTC)
        end_utc = shanghai_tz.localize(datetime.combine(end_date, datetime.max.time())).astimezone(pytz.UTC)
        # between: 在两个时间之间
        conditions.append(model.StockTransaction.transaction_date.between(start_utc, end_utc))

    # 关键字: 物料名称 / 型号 模糊匹配
    if keyword:
        conditions.append(or_(model.Inventory.name.contains(keyword), model.Inventory.type.contains(keyword)))

    # 方向: 1=入库(增加) 2=出库(减少)
    if direction == 1:
        conditions.append(model.StockTransaction.change_quantity > 0)
    elif direction == 2:
        conditions.append(model.StockTransaction.change_quantity < 0)

    # 2. 查总条数（分页用）
    count_stmt = (select(func.count())
                  .select_from(model.StockTransaction)
                  .join(model.Inventory, model.Inventory.id == model.StockTransaction.inventory_id, isouter=True)
                  .where(*conditions))
    total = await db.scalar(count_stmt)

    # 3. 查数据: 降序 + 翻页
    stmt = (select(model.StockTransaction.transaction_date, model.Inventory.name, model.Inventory.type, model.Inventory.unit,
                   model.StockTransaction.order_type,model.StockTransaction.before_quantity, 
                   model.StockTransaction.change_quantity, model.StockTransaction.after_quantity)
            .join(model.Inventory, model.Inventory.id == model.StockTransaction.inventory_id, isouter=True)
            .where(*conditions)
            .order_by(model.StockTransaction.transaction_date.desc())
            .limit(limit).offset(offset))
    result = await db.execute(stmt)   # 执行sql
    # 转成普通 dict, 保证 response_model 校验能按字段名取值
    records = [dict(row) for row in result.mappings().all()]
    return {"total": total, "items": records}
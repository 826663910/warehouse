from fastapi import APIRouter, status, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession  # 异步会话注解
from sqlalchemy import select, exists, or_, func, update, case, and_   # 查询
from sqlalchemy.orm import selectinload # where .... in
from sqlalchemy.exc import SQLAlchemyError
from ..database import get_db  # 会话工厂
from .. import model, schemas, oauth2, unit_convert_tool   # 模型和架构
from typing import Annotated, List, Optional
from datetime import datetime, timezone
import pytz   # pip install pytz

router = APIRouter(
    prefix='/record',
    tags=['RECORD']
)

def attach_display(r):
    """把流水行的【基础单位整数】换算成【显示单位】，挂到 *_display 临时字段上。

    库里 stock_transactions 存的永远是基础单位整数（与 inventory.stock 同口径，
    保证 before ± change = after 恒成立）；显示单位只在读出来时临时换算，不落库。

    物料已被删除时(isouter join 导致 unit 为 None)无法换算，退回原值。
    """
    unit = r.get('unit')
    # unit 缺失（物料已删）时传 None：CONVERSIONS.get(None) 为空表，from_base 走恒等变换不抛错
    cat = r.get('unit_category') if unit else None
    for src, dst in (('before_quantity', 'before_display'),
                     ('change_quantity', 'change_display'),
                     ('after_quantity', 'after_display')):
        v = r.get(src)
        r[dst] = unit_convert_tool.from_base(v, unit, cat) if v is not None else None
    return r


def attach_report_display(r):
    """报表行：把聚合出来的【基础单位】总量换算成【显示单位】。

    每行 = 一个物料，有自己的 unit / unit_category → 可以逐行换算。
    ⚠️ 汇总卡片（summary）做不到：它跨物料求和，斤 + 米 + 个 无法换算成任何单一单位，
       所以 summary 仍然按基础单位聚合，前端不要给它加单位后缀。
    """
    unit = r.get('unit')
    # unit 缺失（物料已删）时传 None：CONVERSIONS.get(None) 为空表，from_base 走恒等变换不抛错
    cat = r.get('unit_category') if unit else None
    for src in ('total_in', 'total_out', 'total_ret', 'total_scr', 'net_change'):
        v = r.get(src)
        r[f'{src}_display'] = unit_convert_tool.from_base(v, unit, cat) if v is not None else None
    return r

# 查询记录
@router.get('/', response_model=schemas.RecordPage)
async def get_record(db: Annotated[AsyncSession, Depends(get_db)],
                     user: Annotated[int, '用户', Depends(oauth2.require_user)],
                     start_day: Optional[str] = None, end_day: Optional[str] = None,
                     keyword: Optional[str] = None, direction: Optional[int] = None,
                     order_type: Optional[int] = None ,limit: int = 10, offset: int = 0):
    """查询出入库流水
    start_day/end_day: 日期范围, 格式 YYYY-MM-DD, 需成对传入
    keyword: 物料名称 / 型号 模糊搜索
    direction: 1=入库(数量增加) 2=出库(数量减少)
    返回: {"total": 总条数, "items": [流水记录, ...]}
    """
    # 1. 公共过滤条件
    # 不筛 Inventory.status：历史流水要完整，物料被禁用/删除后它的流水仍然要能看到
    # （join 是 isouter，物料行缺失时 name/type/unit 为 None，前端已有占位符兜底）
    conditions = []

    # 单据类型
    if order_type is not None:
        conditions.append(model.StockTransaction.order_type == order_type)

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
                  .outerjoin(model.StockOrderDetail,
                             and_(model.StockOrderDetail.order_id == model.StockTransaction.order_id,
                                  model.StockOrderDetail.inventory_id == model.StockTransaction.inventory_id))
                  .where(*conditions))
    total = await db.scalar(count_stmt)

    # 3. 查数据: 降序 + 翻页
    # 关联 stock_order_details 拿到"订单明细的单价"——出库/退货对应销售/退货价，配合流水自己的 unit_cost
    # 能展示「销售金额 / 成本 / 毛利」三件套。join 用 (order_id, inventory_id) 双键匹配，业务上 1:1。
    # unit_category 也要查出来：读完后要用它把基础单位换算成显示单位
    stmt = (select(model.StockTransaction.transaction_date, model.Inventory.code, model.Inventory.name, model.Inventory.type, model.Inventory.unit,
                   model.Inventory.unit_category,
                   model.StockTransaction.order_type, model.StockTransaction.before_quantity,
                   model.StockTransaction.change_quantity, model.StockTransaction.after_quantity,
                   model.StockTransaction.unit_cost,
                   model.StockOrderDetail.unit_price,
                   model.StockTransaction.order_id)
            .join(model.Inventory, model.Inventory.id == model.StockTransaction.inventory_id, isouter=True)
            .outerjoin(model.StockOrderDetail,
                       and_(model.StockOrderDetail.order_id == model.StockTransaction.order_id,
                            model.StockOrderDetail.inventory_id == model.StockTransaction.inventory_id))
            .where(*conditions)
            .order_by(model.StockTransaction.transaction_date.desc())
            .limit(limit).offset(offset))
    result = await db.execute(stmt)   # 执行sql
    # 转成普通 dict, 保证 response_model 校验能按字段名取值
    # attach_display: 基础单位 → 显示单位（*_display 临时字段，不落库）
    records = [attach_display(dict(row)) for row in result.mappings().all()]
    return {"total": total, "items": records}


# 报表：按物料分组聚合
@router.get('/report', response_model=schemas.ReportPage)
async def get_report(db: Annotated[AsyncSession, Depends(get_db)],
                     user: Annotated[int, '用户', Depends(oauth2.require_user)],
                     start_day: Optional[str] = None, end_day: Optional[str] = None,
                     keyword: Optional[str] = None, direction: Optional[int] = None,
                     limit: int = 10, offset: int = 0):
    """按物料聚合的出入库报表
    start_day/end_day: 日期范围, 格式 YYYY-MM-DD, 需成对传入
    keyword: 物料名称 / 型号 模糊搜索
    direction: 1=只统计入库 2=只统计出库（不传 = 全部）
    返回: {"total": 物料数, "items": [{物料信息 + 汇总字段}, ...]}
    """
    # 1. 行级过滤（聚合之前生效：先把不要的流水行筛掉，再按物料分组）
    conditions = []

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

    # 2. 总数 = 分组后的物料数（distinct表示去重), select_from()表示主表
    count_stmt = (select(func.count(func.distinct(model.StockTransaction.inventory_id)))
                  .select_from(model.StockTransaction)  
                  .join(model.Inventory, model.Inventory.id == model.StockTransaction.inventory_id, isouter=True)
                  .where(*conditions))
    total = await db.scalar(count_stmt)

    # 3. 聚合查询：GROUP BY 后 SELECT 只允许出现「分组键 + 聚合函数」
    #    case(...) 条件聚合
    #    语法: case((条件, 值), else_=0)
    stmt = (select(
                # 分组键：物料标识（join 出来的物料信息列也要进 group_by 才合法）
                model.Inventory.code,
                model.Inventory.name,
                model.Inventory.type,
                model.Inventory.unit,
                model.Inventory.unit_category,   # 换算显示单位要用
                # 聚合函数
                func.count().label('tx_count'),
                func.sum(case(
                    (model.StockTransaction.order_type == 1, model.StockTransaction.change_quantity),
                    else_=0
                )).label('total_in'),
                func.sum(case(
                    (model.StockTransaction.order_type == 2, model.StockTransaction.change_quantity),
                    else_=0
                )).label('total_out'),
                # 退货/报废也要 else_=0：不带 ELSE 时 CASE 对不匹配的行返回 NULL，
                # 全 NULL 求和 = NULL，前端拿到的是 None 而不是 0
                func.sum(case(
                    (model.StockTransaction.order_type == 3, model.StockTransaction.change_quantity),
                    else_=0
                )).label('total_ret'),
                func.sum(case(
                    (model.StockTransaction.order_type == 4, model.StockTransaction.change_quantity),
                    else_=0
                )).label('total_scr'),
                func.sum(model.StockTransaction.change_quantity).label('net_change'),
                func.max(model.StockTransaction.transaction_date).label('last_date'),
            )
            .join(model.Inventory, model.Inventory.id == model.StockTransaction.inventory_id, isouter=True)
            .where(*conditions)
            .group_by(model.StockTransaction.inventory_id,
                      model.Inventory.code, model.Inventory.name,
                      model.Inventory.type, model.Inventory.unit,
                      model.Inventory.unit_category)
            # 排序同样只能用分组键或聚合函数：按最近交易时间倒序
            .order_by(func.max(model.StockTransaction.transaction_date).desc())
            .limit(limit).offset(offset))
    result = await db.execute(stmt)   # 执行sql
    # 转成普通 dict, 保证 response_model 校验能按字段名取值
    # attach_report_display: 基础单位 → 显示单位（*_display 临时字段，不落库）
    records = [attach_report_display(dict(row)) for row in result.mappings().all()]

    # 4. 汇总：按【单位赛道】分组聚合（不受 limit/offset 分页影响）
    #    ⚠️ 跨物料求和时各行单位不同（斤 / 米 / 个），混在一起加毫无意义。
    #      但同一赛道内的物料【共享同一个基础单位】，所以能统一换算到该赛道的目标单位：
    #        螺丝(斤) 25000克 + 钢板(公斤) 50000克 = 75000克 → 75 公斤
    #      不同赛道之间仍不能相加（斤 + 米 无解），所以汇总按赛道分行返回。
    #    和上面聚合共用同一套 conditions —— 保证汇总 = 筛选范围内所有流水
    summary_stmt = (select(
                    model.Inventory.unit_category,
                    func.count().label('tx_count'),
                    func.count(func.distinct(model.StockTransaction.inventory_id)).label('item_count'),
                    func.sum(case(
                        (model.StockTransaction.order_type == 1, model.StockTransaction.change_quantity),
                        else_=0
                    )).label('total_in'),
                    func.sum(case(
                        (model.StockTransaction.order_type == 2, model.StockTransaction.change_quantity),
                        else_=0
                    )).label('total_out'),
                    func.sum(case(
                        (model.StockTransaction.order_type == 3, model.StockTransaction.change_quantity),
                        else_=0
                    )).label('total_ret'),
                    func.sum(case(
                        (model.StockTransaction.order_type == 4, model.StockTransaction.change_quantity),
                        else_=0
                    )).label('total_scr'),
                    func.sum(model.StockTransaction.change_quantity).label('net_change'),
                )
                .join(model.Inventory, model.Inventory.id == model.StockTransaction.inventory_id, isouter=True)
                .where(*conditions)
                .group_by(model.Inventory.unit_category))
    summary_rows = (await db.execute(summary_stmt)).mappings().all()

    # 每个赛道换算到自己的目标单位（weight→公斤 / length→米 / volume→升 / count→个）
    by_category = []
    tx_total = 0
    item_total = 0
    for r in summary_rows:
        cat = r['unit_category']
        unit = unit_convert_tool.get_summary_unit(cat)
        row = {
            'category': cat,
            'unit': unit,
            'tx_count': r['tx_count'] or 0,
            'item_count': r['item_count'] or 0,
        }
        # 空结果时 SUM 返回 None，统一成 0 让前端好处理
        for k in ('total_in', 'total_out', 'total_ret', 'total_scr', 'net_change'):
            v = r[k] or 0
            # 没目标单位（other / 物料已删）时无法换算，原样返回基础单位
            row[k] = unit_convert_tool.from_base(v, unit, cat) if unit else v
        by_category.append(row)
        tx_total += row['tx_count']
        item_total += row['item_count']
    # 排序稳定：赛道名升序，None（物料已删/无赛道）排最后
    by_category.sort(key=lambda x: (x['category'] is None, x['category'] or ''))

    summary = {'tx_count': tx_total, 'item_count': item_total, 'by_category': by_category}

    return {"total": total, "items": records, "summary": summary}
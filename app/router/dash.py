from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession   # 异步会话注解
from sqlalchemy import select, func               # 查询, 聚合
from ..database import get_db                     # 会话工厂
from .. import model, schemas, oauth2, unit_convert_tool   # 模型, 架构, 认证
from typing import Annotated
from datetime import datetime, timedelta, date

router = APIRouter(
    prefix='/dashboard',
    tags=['DASHBOARD']
)


def _to_display(v, unit, category):
    """【基础单位】→ 本行物料的【显示单位】（临时字段，不落库）。

    物料已被删除（isouter join 导致 unit 为 None）时传 None：
    CONVERSIONS.get(None) 为空表，from_base 走恒等变换直接返回原值，不会抛错。
    """
    if v is None:
        return None
    return unit_convert_tool.from_base(v, unit, category if unit else None)


@router.get('/stats', response_model=schemas.DashboardStats)
async def get_stats(db: Annotated[AsyncSession, Depends(get_db)],
                    user: Annotated[int, '用户', Depends(oauth2.require_user)]):
    """首页仪表盘聚合统计。

    之前前端的做法: listInventory(limit=10000) + listRecords(limit=10000)
    把全量数据拉到浏览器再在 JS 里 reduce/filter —— 三个问题:
      1. 超 1 万条流水后趋势图/最近流水被静默截断(数字悄悄错)
      2. 全量传输 + inventory 接口每行 join 分类路径/供应商名, 首页根本不用, 全是白算
      3. 数据越多首页越慢
    现在全部在数据库里聚合, 只把数字和小列表(各 8 条)传给前端。
    """
    # ===== 1. 库存统计: 物料种类 + 按【单位赛道】分组的库存总量 =====
    #    原来是一条 SUM(stock) 跨所有物料求和 —— 斤 + 米 + 个 混在一起，数字没有意义。
    #    改成按 unit_category 分组：同赛道内物料共享同一个基础单位，
    #    可统一换算到该赛道的目标单位（weight→公斤 / length→米 / volume→升 / count→个）
    inventory_count = await db.scalar(
        select(func.count()).select_from(model.Inventory)
    ) or 0
    stock_rows = (await db.execute(
        select(model.Inventory.unit_category,
               func.coalesce(func.sum(model.Inventory.stock), 0).label('total'))
        .select_from(model.Inventory)
        .group_by(model.Inventory.unit_category)
    )).mappings().all()
    stock_by_category = []
    for r in stock_rows:
        cat = r['unit_category']
        unit = unit_convert_tool.get_summary_unit(cat)
        v = r['total'] or 0
        stock_by_category.append({
            'category': cat,
            'unit': unit,
            'total': unit_convert_tool.from_base(v, unit, cat) if unit else v,
        })
    stock_by_category.sort(key=lambda x: (x['category'] is None, x['category'] or ''))

    # ===== 2. 供应商 / 分类 数量（只数启用的, 与 /supplier/ /category/ 列表口径一致）=====
    supplier_count = await db.scalar(
        select(func.count()).select_from(model.Supplier).where(model.Supplier.status == 1)
    ) or 0
    category_count = await db.scalar(
        select(func.count()).select_from(model.ProductCategory).where(model.ProductCategory.status == 1)
    ) or 0

    # ===== 3. 预警物料 top8（缺口 = warning - stock 最大的排前面）=====
    # 排序按【基础单位】缺口排（跨行比较，必须同量纲，不能拿 *_display 排）
    warning_rows = (await db.execute(
        select(model.Inventory.id, model.Inventory.code, model.Inventory.name, model.Inventory.type,
               model.Inventory.unit, model.Inventory.unit_category,
               model.Inventory.stock, model.Inventory.warning)
        .where(model.Inventory.warning > 0,
               model.Inventory.stock <= model.Inventory.warning)
        .order_by((model.Inventory.warning - model.Inventory.stock).desc())
        .limit(8)
    )).mappings().all()
    # 展示用：基础单位 → 本行物料的显示单位（*_display 临时字段，不落库）
    warning_items = [
        {**dict(r),
         'stock_display': _to_display(r['stock'], r['unit'], r['unit_category']),
         'warning_display': _to_display(r['warning'], r['unit'], r['unit_category'])}
        for r in warning_rows
    ]

    # ===== 4. 最近流水 top8（和流水页同字段, 只是不要分页参数）=====
    recent_rows = (await db.execute(
        select(model.StockTransaction.transaction_date,
               model.Inventory.name, model.Inventory.type, model.Inventory.unit,
               model.Inventory.unit_category,
               model.StockTransaction.order_type,
               model.StockTransaction.change_quantity,
               model.StockTransaction.after_quantity)
        .join(model.Inventory, model.Inventory.id == model.StockTransaction.inventory_id, isouter=True)
        .order_by(model.StockTransaction.transaction_date.desc(),
                  model.StockTransaction.id.desc())
        .limit(8)
    )).mappings().all()
    # 展示用：同流水页，change/after 换算成本行物料的显示单位
    recent_records = [
        {**dict(r),
         'change_display': _to_display(r['change_quantity'], r['unit'], r['unit_category']),
         'after_display': _to_display(r['after_quantity'], r['unit'], r['unit_category'])}
        for r in recent_rows
    ]

    # ===== 5. 近 7 天趋势: 按天 × 单据类型 × 【单位赛道】聚合总量（绝对值）=====
    #    同第 1 段：跨物料混加无意义，所以多带一个 unit_category 维度，
    #    每组换算到该赛道目标单位。前端按赛道切换显示——
    #    同一天的「公斤」和「米」画不到一根 Y 轴上，只能分赛道看。
    #    DATE(timestamp) 按会话时区(+08)取日期, 和浏览器本地日期一致
    #    where 用本地 naive 时间: MySQL 会话时区是 +08, 字面量按会话时区解释
    start_day = date.today() - timedelta(days=6)   # 今天 - 六天, 含今天共 7 天
    trend_rows = (await db.execute(
        select(func.date(model.StockTransaction.transaction_date).label('day'),
               model.StockTransaction.order_type,
               model.Inventory.unit_category,
               func.sum(func.abs(model.StockTransaction.change_quantity)).label('quantity'))
        # 要按赛道分组，必须 join 物料表才拿得到 unit_category
        .select_from(model.StockTransaction)
        .join(model.Inventory, model.Inventory.id == model.StockTransaction.inventory_id, isouter=True)
        # datetime.combine() ,表示将day和time组装起来
        .where(model.StockTransaction.transaction_date >= datetime.combine(start_day, datetime.min.time()),
               model.StockTransaction.order_type.in_([1, 2, 3, 4]))
        .group_by(func.date(model.StockTransaction.transaction_date),
                  model.StockTransaction.order_type,
                  model.Inventory.unit_category)
    )).mappings().all()
    # day 可能返回 date 对象, 统一转 'YYYY-MM-DD' 字符串, r['xxx] 表示取该健对应的值
    trend = []
    for r in trend_rows:
        cat = r['unit_category']
        unit = unit_convert_tool.get_summary_unit(cat)
        q = r['quantity'] or 0
        trend.append({
            'day': str(r['day']),
            'order_type': r['order_type'],
            'category': cat,
            'unit': unit,
            'quantity': unit_convert_tool.from_base(q, unit, cat) if unit else q,
        })

    return {
        'inventory_count': inventory_count,
        'stock_by_category': stock_by_category,
        'supplier_count': supplier_count,
        'category_count': category_count,
        'warning_items': warning_items,
        'recent_records': recent_records,
        'trend': trend,
    }

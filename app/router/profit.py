"""毛利报表

只统计【出库单】的毛利：
    收入 = 出库单明细的金额（total_amount）
    成本 = 出库数量（显示单位） × 审核那一刻的成本快照

为什么成本不用 inventory.avg_cost（当前成本）：
    它是【当下】的移动加权平均价，之后每进一次货都会变。
    用它的后果是：1 月卖掉的那批货，3 月进货涨价后再看报表，1 月的毛利会跟着缩水。
    报表必须可复现，所以成本取自 stock_transactions.unit_cost ——
    出库审核那一刻写进去的 avg_cost 快照（见 order.py review_order 的出库分支）。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession   # 异步会话注解
from sqlalchemy import select, func, text, and_   # 查询 / 聚合函数
from ..database import get_db                     # 会话工厂
from .. import model, schemas, oauth2, unit_convert_tool
from typing import Annotated, Optional
from datetime import datetime
from decimal import Decimal                       # 金额一律用 Decimal，避免浮点误差
import pytz

router = APIRouter(
    prefix='/profit',
    tags=['PROFIT']
)


@router.get('/trend', response_model=schemas.ProfitTrendOut)
async def profit_trend(db: Annotated[AsyncSession, '数据库会话', Depends(get_db)],
                       user: Annotated[int, '用户', Depends(oauth2.require_user)],
                       start_day: Optional[str] = None, end_day: Optional[str] = None):
    """按月统计毛利趋势（出库单口径）

    start_day / end_day: 日期范围，格式 YYYY-MM-DD, 需成对传入（不传 = 全部时间）
    返回: {"items": [{月份 + 收入/成本/毛利/毛利率}, ...], "total": {整个区间的合计}}

    ⚠️ 决定数字对不对的三条口径：
      1. 只算 order_type=2 (出库）。退货(3)是退给供应商、报废(4)是损失，都不产生收入。
      2. 只算 status=2 (已审核）。草稿既没有成本快照，也不算已实现的销售。
      3. 成本用【历史快照】而不是当前 avg_cost —— 理由见文件顶部。
    """

    # ========== 1. 行级过滤条件（聚合前生效）==========
    conditions = [
        model.StockOrder.order_type == 2,   # 2 = 出库
        model.StockOrder.status == 2,       # 1草稿 2已审 3作废 —— 只认已审
    ]

    # 日期范围：库里 transaction_date 存的是 UTC，而前端日期框选的是北京时间。
    # 所以要把「北京时间的当天 00:00:00 / 23:59:59」换算成 UTC 再 between，
    # 与 record.py 的 /report 保持同一套口径，否则会差 8 小时。
    if start_day and end_day:
        start_date = datetime.strptime(start_day, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_day, '%Y-%m-%d').date()
        shanghai_tz = pytz.timezone('Asia/Shanghai')
        # localize: 给 naive 时间加时区   astimezone: 转成 UTC
        start_utc = shanghai_tz.localize(datetime.combine(start_date, datetime.min.time())).astimezone(pytz.UTC)
        end_utc = shanghai_tz.localize(datetime.combine(end_date, datetime.max.time())).astimezone(pytz.UTC)
        conditions.append(model.StockOrder.transaction_date.between(start_utc, end_utc))

    # ========== 2. 月份表达式 ==========
    # 库里是 UTC，直接 DATE_FORMAT 会按 UTC 分月 → 每月最后 8 小时的单据会被算进上个月。
    # 中国固定 UTC+8 且无夏令时，所以 +8 小时即可；
    # 比 CONVERT_TZ 稳妥，后者依赖 MySQL 的时区表（没装就返回 NULL）。
    # 准备两份：month_col 带别名用于 SELECT，month_expr 不带别名用于 GROUP BY / ORDER BY
    month_expr = func.date_format(
        model.StockOrder.transaction_date + text("INTERVAL 8 HOUR"), '%Y-%m'
    )
    month_col = month_expr.label('month')

    # ========== 3. 成本单价：派生表 ==========
    # stock_transactions.unit_cost 是出库审核那一刻写下的 avg_cost 快照。
    # ⚠️ 同一列在【入库单】里存的是采购单价，语义不同 —— 必须靠 order_type == 2 锁死。
    #
    # 做成「派生表」（FROM 里的子查询）而不是相关子查询，原因有两个：
    #   ① 相关子查询要原样写进 GROUP BY，MySQL 在 ONLY_FULL_GROUP_BY 下对它支持不稳
    #   ② 派生表只扫一次流水表，比每行跑一次子查询快得多
    #
    # 一张单 + 一个物料只会有一条出库流水，所以 max() 只是为了凑聚合函数的形式要求，
    # 实际上每组只有一行，取哪个都一样。
    cost_sq = (
        select(
            model.StockTransaction.order_id.label('order_id'),
            model.StockTransaction.inventory_id.label('inventory_id'),
            func.max(model.StockTransaction.unit_cost).label('unit_cost'),
        )
        .where(model.StockTransaction.order_type == 2)
        .group_by(model.StockTransaction.order_id, model.StockTransaction.inventory_id)
        .subquery()     # 变成可 join 的临时表
    )

    # ========== 4. 聚合查询 ==========
    # 分组键为什么是 (月份, 单位, 赛道, 成本单价) 而不是只有月份？
    #   成本要在 Python 里算：先 from_base(数量 → 显示单位) 再乘单价。
    #   from_base 要求「这一组属于同一个单位」，混着不同单位求和没有意义。
    #   而成本单价必须进分组键：同一个月内如果进过货，前后两次出库的快照价不同，
    #   不能先合并数量再乘一个价。
    #
    # 顺带一提：from_base 是【线性】的（只做除法），所以不同物料只要
    # (单位, 赛道, 成本单价) 相同就可以安全合并求和，无需按物料再拆一层。
    stmt = (
        select(
            month_col,
            model.StockOrderDetail.item_unit.label('unit'),        # 明细里的历史单位快照
            cost_sq.c.unit_cost.label('unit_cost'),
            func.sum(model.StockOrderDetail.quantity).label('quantity'),      # 基础单位数量
            func.sum(model.StockOrderDetail.total_amount).label('revenue'),   # 收入：已是钱，可直接加
        )
        # 不再 join inventory：赛道由 item_unit 反查得到（见第 5 步），
        # 不依赖物料的当前状态，物料被删或赛道被改都不影响老单据的换算结果
        .select_from(model.StockOrderDetail)
        .join(model.StockOrder, model.StockOrder.id == model.StockOrderDetail.order_id)
        # 内连接：只保留有出库流水的明细（草稿单没有流水，反正也被 status == 2 排除了）
        .join(cost_sq, and_(
            cost_sq.c.order_id == model.StockOrderDetail.order_id,
            cost_sq.c.inventory_id == model.StockOrderDetail.inventory_id,
        ))
        .where(*conditions)
        # ⚠️ GROUP BY 里必须写【完整表达式 / 带表名的列】，绝对不能写 select 别名：
        #    MySQL 解析 GROUP BY 时【先查 FROM 里的真实列名，再查 select 别名】
        #    （ORDER BY 正好相反，先查别名）。
        #    所以写 GROUP BY unit 会撞上真实列名，被解析成另一张表的列 → 1055 报错。
        .group_by(
            month_expr,
            model.StockOrderDetail.item_unit,
            cost_sq.c.unit_cost,
        )
        .order_by(month_expr)
    )
    rows = (await db.execute(stmt)).mappings().all()   # mappings() → 每行可按键取值

    # ========== 5. 逐组算成本，再按月份累加 ==========
    # 为什么不在 SQL 里一次算完？
    #   换算表 CONVERSIONS 是 Python 里的常量，数据库看不到，SQL 侧没法 from_base。
    #   所以分工：SQL 负责「筛选 + 分组求和」，Python 负责「换算 + 乘单价」。
    buckets = {}   # {'2026-10': {'revenue': Decimal, 'cost': Decimal}, ...}
    for r in rows:
        # ⚠️ 赛道必须靠 item_unit 反查，不能用物料当前的 unit_category：
        #    明细里的 item_unit 是【下单那一刻】的快照，物料的赛道后来可能改过。
        #    例：原本 count 的螺丝被改成 weight，旧明细 item_unit 还是 '个'，
        #        from_base(qty, '个', 'weight') 会抛 ValueError → 整个报表 500。
        #    反查不到（计数 / 自定义单位）时返回 None → 走恒等变换，与原下单逻辑一致。
        unit = r['unit']
        cat = unit_convert_tool.find_category(unit)
        qty_display = Decimal(str(unit_convert_tool.from_base(r['quantity'] or 0, unit, cat)))
        # 成本 = 显示单位数量 × 当时成本单价
        # 两边都是 Decimal（Numeric 列 / Decimal 运算），不会触发 Decimal × float 的类型错误
        cost = qty_display * Decimal(str(r['unit_cost'] or 0))

        b = buckets.setdefault(r['month'], {'revenue': Decimal('0'), 'cost': Decimal('0')})
        b['revenue'] += Decimal(str(r['revenue'] or 0))
        b['cost'] += cost

    # ========== 6. 组装响应 ==========
    def pack(revenue: Decimal, cost: Decimal):
        """收益 / 成本 → (收入, 成本, 毛利, 毛利率%)"""
        profit = revenue - cost
        # 收入为 0 时毛利率无意义（除零），给 None 让前端显示 '-'
        rate = float(profit / revenue * 100) if revenue else None
        return float(revenue), float(cost), float(profit), rate

    items = []
    total_revenue = Decimal('0')
    total_cost = Decimal('0')
    for month in sorted(buckets):                  # 按月份字符串升序 = 时间正序
        b = buckets[month]
        revenue, cost, profit, rate = pack(b['revenue'], b['cost'])
        items.append({'month': month, 'revenue': revenue, 'cost': cost,
                      'profit': profit, 'profit_rate': rate})
        total_revenue += b['revenue']
        total_cost += b['cost']

    revenue, cost, profit, rate = pack(total_revenue, total_cost)
    return {
        'items': items,
        'total': {'revenue': revenue, 'cost': cost, 'profit': profit, 'profit_rate': rate}
    }

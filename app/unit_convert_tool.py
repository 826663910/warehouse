"""单位换算工具
- CONVERSIONS: 按 category 分组的换算表 (value = 换算到基础单位的乘数）
- to_base: 任意单位 → 基础单位（用于入库/出库时把用户输入变成库存数）
- from_base: 基础单位 → 任意单位（用于详情页展示给用户）
"""
from decimal import Decimal

# 同义词归一化：用户输入"g"也按"克"处理
ALIASES = {
    'g': '克', 'kg': '公斤',
    'ml': '毫升', 'L': '升',
    'cm': '厘米', 'mm': '毫米',
    # '只': '个', '颗': '个',  # 都按"个"算
}

# 基础单位（每个 category 自己定一个最小整数化的）
CONVERSIONS = {
    'weight': {
        '克': 1,         # ← 基础
        '公斤': 1000,
        'kg': 1000,
        '斤': 500,
        '两': 50,
        '钱': 5,
    },
    # count 赛道【没有换算表】：计数单位由用户自己填（个 / 只 / 台 / 袋 / 箱 / 套...），
    #   填什么就存什么、显示什么，不做任何乘除。
    #   原来这里还单独有个 'other' 赛道，行为跟空表一模一样，已合并进来。
    #   ⚠️ 代价：不同计数单位之间无法换算（1 箱 ≠ 12 个），
    #      所以跨物料汇总时「箱 + 台 + 个」依然加不出有意义的数。
    'count': {},
    'length': {
        '毫米': 1,       # ← 基础
        'cm': 10,
        '厘米': 10,
        '米': 1000,
    },
    'volume': {
        '毫升': 1,       # ← 基础
        '升': 1000,
    },
}


def get_package_factor(unit, packages=()):
    """查【物料私有包装】：1 个该包装单位 = 多少基础单位；不是包装单位返回 None。

    包装是物料私有的（螺丝 1箱=24个），跟赛道级换算表（weight: 克/公斤/斤）是两套东西，
    塞不进 CONVERSIONS，只能按物料单独查。
    """
    for p in packages:
        if p.unit_name == unit:
            return p.qty_per_base
    return None


# 把用户填的数量，换算成库存用的整数(用户填的数量, 用户填的单位, 单位类型)
def to_base(qty, unit, category, packages=()):
    """任意单位 → 基础单位（入库/出库时用，返回整数）
    例: to_base(5, '斤', 'weight') = 2500  (克)

    packages = 该物料的包装列表，【优先】于赛道全局表匹配：
        to_base(3, '箱', 'count', [箱=24]) = 72
    不传 packages 时行为与全局表完全一致（建物料的初始库存就是这么用的）。
    """
    # ① 物料私有包装优先：count 赛道没有换算表，包装是它唯一的换算来源，
    #    所以必须在"空表直接返回"之前先查包装，否则 3 箱 会被当成 3
    pkg_factor = get_package_factor(unit, packages)
    if pkg_factor is not None:
        return int(round(qty * pkg_factor))

    # ② 退回赛道全局换算表
    table = CONVERSIONS.get(category, {})
    if not table:                    # count / 未知赛道：无换算，原样返回
        return int(round(qty))
    unit = ALIASES.get(unit, unit)  # 健取值, 如果没有找到, 则返回原值
    factor = CONVERSIONS.get(category, {}).get(unit)  # 现在匹配单位类型, 如果没有返回{}, 有, 再匹配单位的换算系数
    if factor is None:
        raise ValueError(f"单位 {unit} 在类型 {category} 下不能换算")
    return int(round(qty * factor))


# 把库存的整数（基础单位），换算成用户能看懂的"门面数字(用户填的数量, 用户填的单位, 单位类型)
def from_base(qty, unit, category):
    """基础单位 → 任意单位（详情页展示用，返回 float)
    例: from_base(2500, '斤', 'weight') = 5.0
    """
    table = CONVERSIONS.get(category, {})
    if not table:                    # count / 未知赛道：无换算，原样返回
        return qty
    unit = ALIASES.get(unit, unit)
    factor = CONVERSIONS.get(category, {}).get(unit)
    if factor is None:
        raise ValueError(f"单位 {unit} 在类型 {category} 下不能换算")
    return Decimal(str(qty)) / Decimal(str(factor))


def find_category(unit):
    """用【单位名】反查它属于哪个赛道；查不到返回 None（计数 / 自定义单位，无换算表）。

    为什么需要反查：单据明细只存了下单那一刻的历史单位名（item_unit），没存赛道。
    而物料的 unit_category 之后可能被改过，拿【当前】赛道去换算【旧】明细就会对不上 ——
        例：原本 count 的螺丝被改成 weight，旧明细的 item_unit 还是 '个'，
            直接 from_base(qty, '个', 'weight') 就会抛 ValueError。
    单位名本身就是最可靠的线索，所以反过来由它决定赛道。

    注意：目前各赛道的单位名互不重叠（kg 只在 weight），所以反查结果唯一。
    """
    if not unit:
        return None
    u = ALIASES.get(unit, unit)
    for category, table in CONVERSIONS.items():
        if u in table:
            return category
    return None


def get_supported_units(category):
    """返回某 category 下所有可换算的单位（用于前端下拉选项）"""
    return list(CONVERSIONS.get(category, {}).keys())


def get_base_unit(category):
    """返回该赛道的基础单位（换算表里 factor=1 的那个）。
    无换算表的赛道(count 等)返回 None, 由调用方用显示单位兜底。
    """
    for name, factor in CONVERSIONS.get(category, {}).items():
        if factor == 1:
            return name
    return None


# 跨物料汇总时用的目标单位。
#   同一赛道内各物料的显示单位可能不同（螺丝按斤、钢板按公斤、银饰按两），
#   但它们【共享同一个基础单位】，所以能统一换算到一个"够大但不夸张"的单位上：
#     螺丝 25000克 + 钢板 50000克 = 75000克 → ÷1000 → 75 公斤
#   不同赛道之间仍然不能相加（斤 + 米 + 个 无意义），所以汇总必须按赛道分行。
SUMMARY_UNITS = {
    'weight': '公斤',
    'length': '米',
    'volume': '升',
    # count 无换算表，from_base 是恒等变换，所以这个"个"只是个【标签】，
    # 数字 = 各物料原值之和。物料单位统一（都是"个"）时正确；
    # 混用（箱 / 台 / 个）时这个标签是假的 —— 那种情况得按 unit 再细分。
    'count': '个',
}


def get_summary_unit(category):
    """返回该赛道在【跨物料汇总】时的目标单位。
    count 这类无换算表的赛道也在这里取标签；没配过就退回基础单位；都没有则返回 None。
    """
    return SUMMARY_UNITS.get(category) or get_base_unit(category)
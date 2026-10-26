from fastapi import APIRouter, Depends
from typing import Annotated
from .. import oauth2, unit_convert_tool

router = APIRouter(prefix='/units', tags=['UNITS'])


@router.get('/')
async def list_units(category: str,
                     user: Annotated[int, '用户', Depends(oauth2.require_user)]):
    """返回某赛道下所有可换算的单位，供前端"单位"下拉使用。

    GET /units/?category=weight
    → {"category": "weight", "units": ["克", "公斤", "kg", "斤", "两", "钱"]}

    'count'（数量）赛道没有换算表：units 返回空数组，前端回退成文本框，单位由用户自己填。

    factors 一并给前端，是为了让开单页能即时算出「基础单位数量」：
    "库存不足"预警、报废损失预估，都要先把录入值换成基础单位再比较。
    """
    return {
        "category": category,
        "units": unit_convert_tool.get_supported_units(category),
        "factors": unit_convert_tool.CONVERSIONS.get(category, {}),
    }


from fastapi import APIRouter, status, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession  # 异步会话注解
from sqlalchemy import select   # 查询
from ..database import get_db  # 会话工厂
from .. import model, schemas, oauth2   # 模型和架构
from typing import Annotated, List

router = APIRouter(
    prefix='/category',
    tags=['CATEGORY']
)

# 分类列表(左边)
@router.get('/')
async def get_category(db: Annotated[AsyncSession, Depends(get_db)],
                       user: Annotated[int, '用户', Depends(oauth2.require_user)]):
    stmt = (select(model.ProductCategory).where(model.ProductCategory.status==1)
            .order_by(model.ProductCategory.sort_order.desc(), model.ProductCategory.id))
    result = await db.execute(stmt)
    cats = result.scalars().all()
    return cats

@router.post('/')
async def create_category(category: schemas.CategoryCreate, db: Annotated[AsyncSession, Depends(get_db)],
                          user: Annotated[int, '用户', Depends(oauth2.require_user)]):
    """
    parent_id==0, 为父级, 层级为1,
    parent_id==父级的id, 为子级, 层级+1
    """

    # 如果是父级, 层级为1
    if category.parent_id == 0:
        level = 1
    # 否则, 层级+1    
    else:
        parent = await db.get(model.ProductCategory, category.parent_id)
        if not parent:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="父类别不存在")
        level = parent.level + 1

        if level > 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="类别层级不能超过3级")

    # 插入数据
    new_cat = model.ProductCategory(**category.model_dump(), level=level)
    db.add(new_cat)
    await db.commit()
    await db.refresh(new_cat)
    return new_cat


@router.patch('/{id}')
async def update_category(id: int, category: schemas.CategoryUpdate, db: Annotated[AsyncSession, Depends(get_db)],
                          user: Annotated[int, '用户', Depends(oauth2.require_user)]):

    # 查询要更新的类别
    stmt = select(model.ProductCategory).where(model.ProductCategory.id == id)
    result = await db.execute(stmt)
    cat = result.scalar_one_or_none()   # 返回第一条实例
    if not cat:
        raise HTTPException(status_code=404, detail="没有这个类别!")

    # 只取前端实际传入的字段
    update_data = category.model_dump(exclude_unset=True)
    # 如果包含parent_id字段, 则更新层级
    if 'parent_id' in update_data:
        new_parent_id = update_data['parent_id']  # 取出parent_id的值

        # 如果是父级, 层级为1
        if new_parent_id == 0:
            level = 1
        # 否则, 层级+1    
        else:
            parent = await db.get(model.ProductCategory, new_parent_id)   # 查询父类别
            if not parent:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="父类别不存在")

            if new_parent_id == cat.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="父类别不能是自己")

            level = parent.level + 1

            if level > 2:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="类别层级不能超过2级")

        # 更新parent_id和level
        cat.parent_id = new_parent_id
        cat.level = level
            
    # 更新其余类别信息
    for key, value in update_data.items():
        setattr(cat, key, value)
    await db.commit()
    await db.refresh(cat)
    return cat
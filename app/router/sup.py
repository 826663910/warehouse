from fastapi import APIRouter, status, HTTPException, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession  # 异步会话注解
from sqlalchemy import select   # 查询
from ..database import get_db  # 会话工厂
from .. import model, schemas, oauth2   # 模型和架构
from typing import Annotated, List

router = APIRouter(
    prefix='/supplier',
    tags=['SUPPLIER']
)


# 供应商列表(左边)
@router.get('/', response_model=List[schemas.SupplierOut])
async def get_supplier(db: Annotated[AsyncSession, '数据库会话', Depends(get_db)],
                       user: Annotated[int, '用户', Depends(oauth2.require_user)]):
    # 查询供应商, 过滤出状态为1的, 再按排序值降序, 供应商id升序
    stmt = select(model.Supplier).where(model.Supplier.status==1).order_by(model.Supplier.sort_order.desc(), model.Supplier.id)
    result = await db.execute(stmt)  # 执行sql
    sups = result.scalars().all()   # 返回列表
    return sups


# 创建供应商
@router.post('/')
async def create_supplier(supplier: schemas.SupplierCreate, db: Annotated[AsyncSession, Depends(get_db)],
                          user: Annotated[int, '用户', Depends(oauth2.require_user)]):
    # 创建新的供应商记录
    new_supplier = model.Supplier(**supplier.model_dump())
    db.add(new_supplier)
    await db.commit()
    await db.refresh(new_supplier)
    return new_supplier


# 修改供应商
@router.patch('/{id}')
async def update_supplier(id: int, check_supplier: schemas.SupplierCreate, 
                          db: Annotated[AsyncSession, Depends(get_db)],
                          user: Annotated[int, '用户', Depends(oauth2.require_role)]):
    stmt = select(model.Supplier).where(model.Supplier.id == id)
    result = await db.execute(stmt)
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="没有这个供应商!")
    
    # 更新供应商信息
    for key, value in check_supplier.model_dump().items():
        setattr(supplier, key, value)
    
    await db.commit()
    await db.refresh(supplier)
    return supplier

@router.delete('/{id}')
async def delete_supplier(id: int, db: Annotated[AsyncSession, Depends(get_db)],
                          user: Annotated[int, '用户', Depends(oauth2.require_role)]):
    # 查询要删除的供应商
    stmt = select(model.Supplier).where(model.Supplier.id == id)
    result = await db.execute(stmt)         # 执行sql
    supplier = result.scalar_one_or_none()  # 返回第一条实例
    if not supplier:
        raise HTTPException(status_code=404, detail="没有这个供应商!")

    # 引用校验：还有启用状态的物料挂在这个供应商上时不许删
    # （前端各处的供应商下拉只取 status=1，删掉后这些物料的供应商名会显示不出来）
    used = await db.scalar(
        select(model.Inventory.id)
        .where(model.Inventory.supplier_id == id, model.Inventory.status == 1)
        .limit(1)
    )
    if used:
        raise HTTPException(status_code=400, detail="该供应商下还有启用状态的物料, 请先处理物料后再删除!")

    supplier.status = 0   # 逻辑删除
    await db.commit()     # 提交
    return Response(status_code=status.HTTP_204_NO_CONTENT)
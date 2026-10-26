from fastapi import APIRouter, HTTPException, status, Depends
from ..database import get_db
from .. import model, schemas, oauth2
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Annotated, List

router = APIRouter(
    prefix='/customer',
    tags=['CUSTOMER']
)

@router.get('/', response_model=List[schemas.CustomerOut])
async def get_customer(db: Annotated[AsyncSession, Depends(get_db)],
                       user: Annotated[int, '用户', Depends(oauth2.require_user)]):
    stmt = select(model.Customer).where(model.Customer.status==1)
    result = await db.execute(stmt)
    customers = result.scalars().all()
    return customers


@router.post('/')
async def create_customer(customer: schemas.CustomerCreate, db: Annotated[AsyncSession, Depends(get_db)],
                          user: Annotated[int, '用户', Depends(oauth2.require_user)]):
    new_customer = model.Customer(**customer.model_dump())
    db.add(new_customer)
    await db.commit()
    await db.refresh(new_customer)
    return new_customer


@router.patch('/{id}')
async def update_customer(id: int, customer_data: schemas.CustomerUpdate, db: Annotated[AsyncSession, Depends(get_db)],
                          user: Annotated[int, '用户', Depends(oauth2.require_role)]):
    stmt = select(model.Customer).where(model.Customer.id == id)
    result = await db.execute(stmt)
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="没有这个客户!")

    # 更新客户信息
    for key, value in customer_data.model_dump().items():
        setattr(customer, key, value)

    await db.commit()
    await db.refresh(customer)
    return customer


@router.delete('/{id}')
async def delete_customer(id: int, db: Annotated[AsyncSession, Depends(get_db)],
                          user: Annotated[int, '用户', Depends(oauth2.require_role)]):
    # 逻辑删除：和 supplier 保持一致（status=0），而不是物理删除
    cust = await db.get(model.Customer, id)
    if cust is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='没有这个客户!')

    # 引用校验：被单据引用时不许删（前端下拉只显示 status=1，删了后历史单据的"客户"列会显示不出名字）
    used = await db.scalar(
        select(model.StockOrder.id)
        .where(model.StockOrder.customer_id == id)
        .limit(1)
    )
    if used:
        raise HTTPException(status_code=400, detail="该客户下还有单据, 请先处理单据后再删除!")

    cust.status = 0   # 逻辑删除
    await db.commit()
    return {"message": "删除成功"}

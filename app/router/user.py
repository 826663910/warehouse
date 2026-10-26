from fastapi import APIRouter, status, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession   # 异步session注解
from sqlalchemy import select, func               # 查询, 聚合
from .. import schemas, model, utils, oauth2      # 模型, 模型, 工具, 认证
from ..database import get_db                     # 操作数据库
from typing import Annotated, List

# 实例化路由器
router = APIRouter(
    prefix="/users",    # 路径前缀
    tags=["users"],     # 标签
)

# level -> role 映射（role 仅展示用，权限判断一律走 level）
ROLE_BY_LEVEL = {1: 'user', 2: 'admin', 3: 'super_admin'}


# 创建账号（仅超管）
@router.post('/', response_model=schemas.UserOut)
async def create_user(user: schemas.CreateUser,
                      db: Annotated[AsyncSession, Depends(get_db)],
                      current_user: Annotated[model.User, Depends(oauth2.require_super_admin)]):
    # 级别合法性
    if user.level not in ROLE_BY_LEVEL:
        raise HTTPException(status_code=400, detail="level 只能是 1(普通用户) / 2(管理员) / 3(超级管理员)")

    # 用户名查重（之前用一揽子 except 兜底 409，任何错误都报"已存在"，掩盖真实问题）
    exists = await db.scalar(
        select(model.User.id).where(model.User.username == user.username).limit(1)
    )
    if exists:
        raise HTTPException(status_code=409, detail=f"用户名「{user.username}」已存在")

    new_user = model.User(
        username=user.username,
        password=utils.hash(user.password),
        level=user.level,
        role=ROLE_BY_LEVEL[user.level]   # role 由 level 派生，不信任前端
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


# 用户列表（仅超管）
@router.get('/', response_model=List[schemas.UserOut])
async def get_list_user(db: Annotated[AsyncSession, Depends(get_db)],
                        current_user: Annotated[model.User, Depends(oauth2.require_super_admin)]):
    stmt = select(model.User).order_by(model.User.id)
    result = await db.execute(stmt)
    return result.scalars().all()


# 获取指定用户（仅超管）
@router.get('/{id}', response_model=schemas.UserOut)
async def get_user(id: int, db: Annotated[AsyncSession, Depends(get_db)],
                   current_user: Annotated[model.User, Depends(oauth2.require_super_admin)]):
    stmt = select(model.User).where(model.User.id == id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    return user


# 更新账号：改密码 / 改级别（仅超管）
@router.patch('/{id}', response_model=schemas.UserOut)
async def update_user(id: int, data: schemas.UserUpdate,
                      db: Annotated[AsyncSession, Depends(get_db)],
                      current_user: Annotated[model.User, Depends(oauth2.require_super_admin)]):
    stmt = select(model.User).where(model.User.id == id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    update_data = data.model_dump(exclude_unset=True)   # 只取传了的字段

    # 改级别
    if 'level' in update_data:
        new_level = update_data['level']
        if new_level not in ROLE_BY_LEVEL:
            raise HTTPException(status_code=400, detail="level 只能是 1(普通用户) / 2(管理员) / 3(超级管理员)")
        # 不能降自己：把自己从超管降级后，这个页面就进不来了，也没人能再管理账号
        if id == current_user.id and new_level < 3:
            raise HTTPException(status_code=400, detail="不能降级自己的账号（否则将无人能管理账号）")
        user.level = new_level
        user.role = ROLE_BY_LEVEL[new_level]   # role 跟随 level 同步

    # 改密码
    if update_data.get('password'):
        user.password = utils.hash(update_data['password'])

    await db.commit()
    await db.refresh(user)
    return user


# 删除账号（仅超管）
@router.delete('/{id}')
async def delete_user(id: int, db: Annotated[AsyncSession, Depends(get_db)],
                      current_user: Annotated[model.User, Depends(oauth2.require_super_admin)]):
    # 不能删自己
    if id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录的账号")

    stmt = select(model.User).where(model.User.id == id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    # 不能删最后一个超管（否则全系统没人能进账号管理）
    if user.level >= 3:
        super_count = await db.scalar(
            select(func.count()).select_from(model.User).where(model.User.level >= 3)
        )
        if super_count <= 1:
            raise HTTPException(status_code=400, detail="必须保留至少一个超级管理员")

    # 物理删除是安全的：单据表 created_by 存的是用户名字符串（非外键），历史单据不受影响
    await db.delete(user)
    await db.commit()
    return {"message": "删除成功"}

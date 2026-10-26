from fastapi import FastAPI
from contextlib import asynccontextmanager  # 异步上下文管理器
from fastapi.middleware.cors import CORSMiddleware  # cors中间件
from sqlalchemy import text
from .database import init_db, engine, check_db_connection  # 初始化数据库, 获取session, 引擎
from .router import user, auth, sup, cate, inventory, order, record, cust, dash, units, profit
from fastapi.middleware.cors import CORSMiddleware  # 跨域中间件

# 在应用启动时, 调用init_db函数, 来执行create_all, 完成后自动关闭
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 先检测数据库是否可连接
    if await check_db_connection():
        print("数据库连接成功")
        await init_db()
        await seed_super_admin()
    else:
        print("警告：数据库连接失败！")
    yield
    await engine.dispose()


async def seed_super_admin():
    """初始超管账号：用户表为空时创建 admin/admin123 (已有任何用户则跳过，不动现有数据)"""
    from sqlalchemy import select, func
    from .database import async_session_maker
    from . import model, utils
    async with async_session_maker() as session:
        count = await session.scalar(select(func.count()).select_from(model.User))
        if count == 0:
            session.add(model.User(
                username='admin',
                password=utils.hash('admin123'),
                level=3,
                role='super_admin'
            ))
            await session.commit()
            print("已创建初始超级管理员: admin / admin123 （请登录后尽快修改密码）")

app = FastAPI(lifespan=lifespan)

# origins = [
#     "https://.tiangolo.com",
#     "https://.tiangolo.com",
#     "https://",
#     "https://:8080",
# ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router)
app.include_router(user.router)
app.include_router(sup.router)
app.include_router(cate.router)
app.include_router(inventory.router)
app.include_router(order.router)
app.include_router(record.router)
app.include_router(cust.router)
app.include_router(dash.router)
app.include_router(units.router)
app.include_router(profit.router)

 # 前端启动 cd d:/warehouse/web  npm run dev

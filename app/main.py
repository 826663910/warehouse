from fastapi import FastAPI
from contextlib import asynccontextmanager  # 异步上下文管理器
from fastapi.middleware.cors import CORSMiddleware  # cors中间件
from sqlalchemy import text
from .database import init_db, engine, check_db_connection  # 初始化数据库, 获取session, 引擎
from .router import user, auth, sup, cate, inventory, order, record
from fastapi.middleware.cors import CORSMiddleware  # 跨域中间件

# 在应用启动时, 调用init_db函数, 来执行create_all, 完成后自动关闭
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 先检测数据库是否可连接
    if await check_db_connection():
        print("数据库连接成功")
        await init_db()
    else:
        print("警告：数据库连接失败！")
    yield
    await engine.dispose()

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

 # 前端启动 cd d:/warehouse/web  npm run dev

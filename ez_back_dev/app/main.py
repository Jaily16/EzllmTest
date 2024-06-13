from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import router
from langserve import add_routes

app = FastAPI(
    title="EzllmTest BackEnd API",
    description="基于LLM驱动的软件测试计划和用例生成平台的后端api接口 "
)

app.include_router(router)
# add_routes(app, chain, path="/llm/test")

# 将配置挂在到app上,解决跨域问题
app.add_middleware(
    CORSMiddleware,
    # 这里配置允许跨域访问的前端地址
    allow_origins=["*"],
    # 跨域请求是否支持 cookie， 如果这里配置true，则allow_origins不能配置*
    allow_credentials=False,
    # 支持跨域的请求类型，可以单独配置get、post等，也可以直接使用通配符*表示支持所有
    allow_methods=["*"],
    allow_headers=["*"],
)
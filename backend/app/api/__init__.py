from fastapi import APIRouter

from app.api.lua_generator import router as lua_router

api_v1_router = APIRouter(prefix="")

api_v1_router.include_router(lua_router)

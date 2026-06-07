from aiogram import Router

from bot.handlers import admin, user


def setup_routers() -> Router:
    router = Router()
    router.include_router(user.router)
    router.include_router(admin.router)
    return router

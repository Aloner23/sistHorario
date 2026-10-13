"""Entrada para Vercel (runtime de Python): expone la app ASGI."""

from app.main import app

__all__ = ["app"]

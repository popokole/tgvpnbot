"""Агрегирующий сервис платежей — только YooKassa."""

from __future__ import annotations

from importlib import import_module
from typing import Any

import structlog
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.payment import (
    PaymentCommonMixin,
    YooKassaPaymentMixin,
)
from app.services.yookassa_service import YooKassaService


logger = structlog.get_logger(__name__)


# --- CRUD-алиасы для YooKassa ---


async def create_yookassa_payment(*args, **kwargs):
    yk_crud = import_module('app.database.crud.yookassa')
    return await yk_crud.create_yookassa_payment(*args, **kwargs)


async def update_yookassa_payment_status(*args, **kwargs):
    yk_crud = import_module('app.database.crud.yookassa')
    return await yk_crud.update_yookassa_payment_status(*args, **kwargs)


async def link_yookassa_payment_to_transaction(*args, **kwargs):
    yk_crud = import_module('app.database.crud.yookassa')
    return await yk_crud.link_yookassa_payment_to_transaction(*args, **kwargs)


async def get_yookassa_payment_by_id(*args, **kwargs):
    yk_crud = import_module('app.database.crud.yookassa')
    return await yk_crud.get_yookassa_payment_by_id(*args, **kwargs)


async def get_yookassa_payment_by_local_id(*args, **kwargs):
    yk_crud = import_module('app.database.crud.yookassa')
    return await yk_crud.get_yookassa_payment_by_local_id(*args, **kwargs)


async def create_transaction(*args, **kwargs):
    transaction_crud = import_module('app.database.crud.transaction')
    return await transaction_crud.create_transaction(*args, **kwargs)


async def get_transaction_by_external_id(*args, **kwargs):
    transaction_crud = import_module('app.database.crud.transaction')
    return await transaction_crud.get_transaction_by_external_id(*args, **kwargs)


async def add_user_balance(*args, **kwargs):
    user_crud = import_module('app.database.crud.user')
    return await user_crud.add_user_balance(*args, **kwargs)


async def get_user_by_id(*args, **kwargs):
    user_crud = import_module('app.database.crud.user')
    return await user_crud.get_user_by_id(*args, **kwargs)


async def get_user_by_telegram_id(*args, **kwargs):
    user_crud = import_module('app.database.crud.user')
    return await user_crud.get_user_by_telegram_id(*args, **kwargs)


class PaymentService(
    PaymentCommonMixin,
    YooKassaPaymentMixin,
):
    """Платёжный сервис — только YooKassa с поддержкой рекуррентных платежей."""

    def __init__(self, bot: Bot | None = None) -> None:
        self.bot = bot
        self.yookassa_service = YooKassaService(bot_username_for_default_return=settings.BOT_USERNAME) if settings.is_yookassa_enabled() else None

        logger.debug(
            'PaymentService инициализирован (только YooKassa)',
            yookassa_enabled=bool(self.yookassa_service),
        )

    async def create_guest_payment(
        self,
        db: AsyncSession,
        *,
        amount_kopeks: int,
        payment_method: str,
        description: str,
        purchase_token: str,
        return_url: str,
    ) -> dict[str, Any] | None:
        """Создаёт платёж для гостевой покупки через YooKassa."""
        if self.yookassa_service is None:
            logger.warning('YooKassa не настроен, гостевой платёж невозможен')
            return None

        guest_metadata: dict[str, Any] = {
            'purpose': 'guest_purchase',
            'purchase_token': purchase_token,
            'source': 'landing',
        }

        if payment_method in ('yookassa', 'yookassa_card'):
            result = await self.create_yookassa_payment(
                db=db,
                user_id=None,
                amount_kopeks=amount_kopeks,
                description=description,
                metadata=guest_metadata,
                return_url=return_url,
            )
        elif payment_method == 'yookassa_sbp':
            result = await self.create_yookassa_sbp_payment(
                db=db,
                user_id=None,
                amount_kopeks=amount_kopeks,
                description=description,
                metadata=guest_metadata,
                return_url=return_url,
            )
        else:
            logger.warning('Неподдерживаемый метод оплаты', payment_method=payment_method)
            return None

        if result:
            return {
                'payment_url': result.get('confirmation_url'),
                'payment_id': result.get('yookassa_payment_id'),
                'provider': 'yookassa',
            }
        return None

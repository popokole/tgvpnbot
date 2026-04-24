"""Сервис напоминаний об истечении подписки.

Расписание напоминаний (по Figma):
- За 24 часа
- За 6 часов (только если не ночь: 22:00–08:00 по timezone пользователя)
- За 1 час
- За 10 минут
- После истечения: "Ключ деактивирован"
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from aiogram import Bot
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Subscription, SubscriptionStatus, User


logger = structlog.get_logger(__name__)

# Пороги напоминаний (в минутах до истечения)
_REMINDER_WINDOWS = [
    (60 * 24,  60 * 24 - 30, 'remind_24h'),   # за 24ч (окно ±30 мин)
    (60 * 6,   60 * 6 - 30,  'remind_6h'),    # за 6ч  (окно ±30 мин)
    (60,       45,            'remind_1h'),    # за 1ч  (окно ±15 мин)
    (10,       5,             'remind_10m'),   # за 10мин (окно ±5 мин)
]

# Флаги напоминаний хранятся в metadata подписки
_FLAG_PREFIX = 'lipton_reminder_sent_'


def _is_night(hour: int) -> bool:
    """Считаем ночью 22:00–08:00."""
    return hour >= 22 or hour < 8


def _build_reminder_text(minutes_left: int, key: str) -> str:
    if key == 'remind_24h':
        return (
            '⏰ <b>Подписка истекает завтра!</b>\n\n'
            'До окончания подписки осталось ~24 часа.\n'
            'Продлите сейчас, чтобы не потерять доступ.'
        )
    if key == 'remind_6h':
        return (
            '⚠️ <b>До конца подписки 6 часов</b>\n\n'
            'Успейте продлить подписку, чтобы VPN работал без перерыва.'
        )
    if key == 'remind_1h':
        return (
            '🚨 <b>До конца подписки 1 час</b>\n\n'
            'Осталось совсем мало! Продлите прямо сейчас.'
        )
    if key == 'remind_10m':
        return (
            '🔴 <b>Подписка истекает через 10 минут!</b>\n\n'
            'Продлите немедленно, чтобы не потерять доступ.'
        )
    return '⏰ Скоро истекает подписка.'


async def send_expiry_reminders(db: AsyncSession, bot: Bot) -> dict:
    """Проходит по активным подпискам и отправляет напоминания."""
    from app.keyboards.lipton import get_expiry_reminder_keyboard

    now = datetime.now(UTC)
    stats = {'checked': 0, 'sent': 0, 'errors': 0, 'skipped_night': 0}

    result = await db.execute(
        select(Subscription)
        .where(
            and_(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.expire_at.isnot(None),
                Subscription.expire_at > now,
                Subscription.expire_at <= now + timedelta(hours=25),
            )
        )
        .options(selectinload(Subscription.user))
    )
    subscriptions = result.scalars().all()
    stats['checked'] = len(subscriptions)

    for sub in subscriptions:
        user: User | None = sub.user
        if not user or not user.telegram_id:
            continue

        minutes_left = int((sub.expire_at - now).total_seconds() / 60)

        for threshold_max, threshold_min, reminder_key in _REMINDER_WINDOWS:
            if not (threshold_min <= minutes_left <= threshold_max):
                continue

            flag_key = f'{_FLAG_PREFIX}{reminder_key}'
            meta = sub.metadata_json or {}

            if meta.get(flag_key):
                break  # уже отправляли

            # Пропускаем 6h-напоминание ночью
            if reminder_key == 'remind_6h':
                user_tz = getattr(user, 'timezone', 'UTC') or 'UTC'
                try:
                    from zoneinfo import ZoneInfo
                    local_hour = now.astimezone(ZoneInfo(user_tz)).hour
                except Exception:
                    local_hour = now.hour
                if _is_night(local_hour):
                    stats['skipped_night'] += 1
                    break

            text = _build_reminder_text(minutes_left, reminder_key)

            try:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=text,
                    reply_markup=get_expiry_reminder_keyboard(),
                    parse_mode='HTML',
                )
                # Сохраняем флаг
                meta[flag_key] = now.isoformat()
                sub.metadata_json = meta
                await db.commit()
                stats['sent'] += 1
                logger.info(
                    'Expiry reminder sent',
                    user_id=user.id,
                    reminder_key=reminder_key,
                    minutes_left=minutes_left,
                )
            except Exception as e:
                stats['errors'] += 1
                logger.warning('Failed to send expiry reminder', user_id=user.id, error=e)

            break  # отправляем только одно напоминание за цикл

    return stats


async def send_expired_notifications(db: AsyncSession, bot: Bot) -> dict:
    """Уведомляет пользователей, у которых только что истёк ключ (деактивирован)."""
    from app.keyboards.lipton import get_expired_keyboard

    now = datetime.now(UTC)
    recently_expired = now - timedelta(minutes=15)
    stats = {'checked': 0, 'sent': 0, 'errors': 0}

    result = await db.execute(
        select(Subscription)
        .where(
            and_(
                Subscription.status == SubscriptionStatus.EXPIRED,
                Subscription.expire_at.isnot(None),
                Subscription.expire_at >= recently_expired,
                Subscription.expire_at <= now,
            )
        )
        .options(selectinload(Subscription.user))
    )
    subscriptions = result.scalars().all()
    stats['checked'] = len(subscriptions)

    for sub in subscriptions:
        user: User | None = sub.user
        if not user or not user.telegram_id:
            continue

        meta = sub.metadata_json or {}
        if meta.get(f'{_FLAG_PREFIX}expired'):
            continue

        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=(
                    '❌ <b>Ключ деактивирован</b>\n\n'
                    'Ваша подписка истекла. VPN-доступ отключён.\n\n'
                    'Выберите тариф, чтобы возобновить доступ.'
                ),
                reply_markup=get_expired_keyboard(),
                parse_mode='HTML',
            )
            meta[f'{_FLAG_PREFIX}expired'] = now.isoformat()
            sub.metadata_json = meta
            await db.commit()
            stats['sent'] += 1
        except Exception as e:
            stats['errors'] += 1
            logger.warning('Failed to send expiry notification', user_id=user.id, error=e)

    return stats

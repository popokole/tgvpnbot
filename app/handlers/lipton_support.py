"""Handler раздела Поддержка LiptonVPN — включая отвязку карты."""

from __future__ import annotations

import structlog
from aiogram import Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.user import get_user_by_telegram_id
from app.keyboards.lipton import (
    get_back_keyboard,
    get_confirm_keyboard,
    get_confirm_unlink_card_keyboard,
    get_device_selection_keyboard,
    get_support_keyboard,
)


logger = structlog.get_logger(__name__)


def _card_last4(user) -> str | None:
    methods = getattr(user, 'saved_payment_methods', None)
    if methods:
        active = [c for c in methods if c.is_active]
        if active:
            return active[0].card_last4
    return None


def _support_url() -> str:
    return getattr(settings, 'SUPPORT_URL', None) or getattr(settings, 'SUPPORT_CHAT_LINK', None) or ''


# ---------------------------------------------------------------------------
# Главная страница поддержки
# ---------------------------------------------------------------------------

async def show_support(callback: types.CallbackQuery, db: AsyncSession):
    await callback.answer()
    user = await get_user_by_telegram_id(db, callback.from_user.id)
    card_last4 = _card_last4(user) if user else None

    card_line = f'\n💳 Привязанная карта: •••• {card_last4}' if card_last4 else ''
    text = f'💬 <b>Поддержка LiptonVPN</b>\n\nВыберите тему обращения:{card_line}'

    try:
        await callback.message.edit_text(
            text, reply_markup=get_support_keyboard(has_card=card_last4 is not None), parse_mode='HTML'
        )
    except Exception:
        await callback.message.answer(
            text, reply_markup=get_support_keyboard(has_card=card_last4 is not None), parse_mode='HTML'
        )


# ---------------------------------------------------------------------------
# Подразделы поддержки
# ---------------------------------------------------------------------------

async def handle_support_about(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        '🛡 <b>О сервисе LiptonVPN</b>\n\n'
        'LiptonVPN — быстрый и надёжный VPN-сервис для обхода блокировок.\n\n'
        '✅ Протокол VLESS / XTLS\n'
        '✅ Приложение v2raytun на всех платформах\n'
        '✅ Серверы в нескольких странах\n'
        '✅ Специальный сервер с обходом DPI для России\n'
        '✅ Техподдержка 7 дней в неделю',
        reply_markup=get_back_keyboard('show_support'),
        parse_mode='HTML',
    )


async def handle_support_install(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        '📲 <b>Как установить VPN</b>\n\n'
        'Выберите устройство — я пришлю пошаговую инструкцию\n'
        'и ссылку на скачивание приложения v2raytun:',
        reply_markup=get_device_selection_keyboard(),
        parse_mode='HTML',
    )


async def handle_support_suggestions(callback: types.CallbackQuery):
    await callback.answer()
    url = _support_url()
    text = (
        '💡 <b>Предложения</b>\n\n'
        'Есть идея как сделать сервис лучше?\n'
        'Напишите нам — мы читаем все сообщения!'
    )
    if url:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='📩 Написать предложение', url=url)],
            [InlineKeyboardButton(text='◀️ Назад', callback_data='show_support')],
        ])
    else:
        kb = get_back_keyboard('show_support')
    await callback.message.answer(text, reply_markup=kb, parse_mode='HTML')


async def handle_support_cancel_sub(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        '❌ <b>Отмена подписки</b>\n\n'
        'Вы уверены, что хотите отменить автопродление?\n\n'
        '<i>Текущая подписка останется активной до конца оплаченного периода.</i>',
        reply_markup=get_confirm_keyboard(
            confirm_callback='confirm_cancel_sub',
            cancel_callback='show_support',
            confirm_text='✅ Да, отменить',
            cancel_text='◀️ Назад',
        ),
        parse_mode='HTML',
    )


async def confirm_cancel_sub(callback: types.CallbackQuery, db: AsyncSession):
    await callback.answer()
    user = await get_user_by_telegram_id(db, callback.from_user.id)
    if user and hasattr(user, 'autopay_enabled'):
        user.autopay_enabled = False
        await db.commit()
        logger.info('User cancelled autopay', user_id=user.id)

    await callback.message.edit_text(
        '✅ Автопродление отключено.\n\n'
        'Подписка остаётся активной до конца оплаченного периода.\n'
        'Новых списаний не будет.',
        reply_markup=get_back_keyboard('back_to_menu'),
    )


async def handle_support_contact(callback: types.CallbackQuery):
    await callback.answer()
    url = _support_url()
    if url:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='📞 Написать в поддержку', url=url)],
            [InlineKeyboardButton(text='◀️ Назад', callback_data='show_support')],
        ])
        await callback.message.answer(
            '📞 <b>Техническая поддержка</b>\n\n'
            'Нажмите кнопку ниже, чтобы написать в поддержку.\n'
            'Среднее время ответа: 30 минут.',
            reply_markup=kb,
            parse_mode='HTML',
        )
    else:
        await callback.message.answer(
            '📞 <b>Техническая поддержка</b>\n\n'
            'Ссылка на поддержку не настроена. Обратитесь к администратору.',
            reply_markup=get_back_keyboard('show_support'),
            parse_mode='HTML',
        )


# ---------------------------------------------------------------------------
# Отвязка карты
# ---------------------------------------------------------------------------

async def handle_unlink_card(callback: types.CallbackQuery, db: AsyncSession):
    await callback.answer()
    user = await get_user_by_telegram_id(db, callback.from_user.id)
    card_last4 = _card_last4(user) if user else None

    if not card_last4:
        await callback.answer('У вас нет привязанной карты', show_alert=True)
        return

    await callback.message.answer(
        f'💳 <b>Отвязать карту •••• {card_last4}?</b>\n\n'
        '⚠️ После отвязки автоматические списания прекратятся.\n'
        'Подписку нужно будет продлевать вручную.',
        reply_markup=get_confirm_unlink_card_keyboard(),
        parse_mode='HTML',
    )


async def confirm_unlink_card(callback: types.CallbackQuery, db: AsyncSession):
    await callback.answer()
    user = await get_user_by_telegram_id(db, callback.from_user.id)
    if not user:
        await callback.answer('Пользователь не найден', show_alert=True)
        return

    unlinked_any = False
    for card in getattr(user, 'saved_payment_methods', []):
        if card.is_active:
            card.is_active = False
            unlinked_any = True

    if hasattr(user, 'autopay_enabled'):
        user.autopay_enabled = False

    if unlinked_any:
        await db.commit()
        logger.info('User unlinked card', user_id=user.id)
        await callback.message.edit_text(
            '✅ <b>Карта отвязана</b>\n\n'
            'Автоматические списания остановлены.\n'
            'Текущая подписка действует до конца оплаченного периода.',
            reply_markup=get_back_keyboard('back_to_menu'),
            parse_mode='HTML',
        )
    else:
        await callback.answer('Привязанная карта не найдена', show_alert=True)


# ---------------------------------------------------------------------------
# Регистрация
# ---------------------------------------------------------------------------

def register_lipton_support_handlers(dp: Dispatcher):
    dp.callback_query.register(show_support,             F.data == 'show_support')
    dp.callback_query.register(handle_support_about,     F.data == 'support:about')
    dp.callback_query.register(handle_support_install,   F.data == 'support:install')
    dp.callback_query.register(handle_support_suggestions, F.data == 'support:suggestions')
    dp.callback_query.register(handle_support_cancel_sub,  F.data == 'support:cancel_sub')
    dp.callback_query.register(confirm_cancel_sub,       F.data == 'confirm_cancel_sub')
    dp.callback_query.register(handle_support_contact,   F.data == 'support:contact')
    dp.callback_query.register(handle_unlink_card,       F.data == 'support:unlink_card')
    dp.callback_query.register(confirm_unlink_card,      F.data == 'confirm_unlink_card')

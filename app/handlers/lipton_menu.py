"""Основной handler LiptonVPN — главное меню, тарифы, профиль, обход глушилок."""

from __future__ import annotations

import structlog
from aiogram import Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.subscription import get_subscription_by_user_id as get_active_subscription_by_user_id
from app.database.crud.user import get_user_by_telegram_id as _get_user_by_tg_id
from app.database.crud.user import get_user_by_telegram_id
from app.keyboards.lipton import (
    get_back_keyboard,
    get_bypass_keyboard,
    get_main_menu_keyboard,
    get_profile_keyboard,
    get_tariffs_keyboard,
    get_yookassa_pay_keyboard,
)
from app.utils.timezone import format_local_datetime


logger = structlog.get_logger(__name__)

_TARIFF_CATALOG = {
    '1m':     {'label': '1 месяц',         'days': 30,  'price_rub': 159,  'price_kopeks': 15900},
    '3m':     {'label': '3 месяца',         'days': 90,  'price_rub': 450,  'price_kopeks': 45000},
    '12m':    {'label': '12 месяцев',       'days': 365, 'price_rub': 1219, 'price_kopeks': 121900},
    'always': {'label': 'Всегда на связи',  'days': 30,  'price_rub': 499,  'price_kopeks': 49900},
}


# ---------------------------------------------------------------------------
# Общие утилиты
# ---------------------------------------------------------------------------

def _card_last4(user) -> str | None:
    methods = getattr(user, 'saved_payment_methods', None)
    if methods:
        active = [c for c in methods if c.is_active]
        if active:
            return active[0].card_last4
    return None


def _build_menu_content(sub, user, name: str):
    """Возвращает (text, keyboard) для главного меню."""
    has_sub = bool(sub)
    is_admin = settings.is_admin(user.telegram_id) if user else False

    if sub and sub.expire_at:
        tz = getattr(user, 'timezone', 'UTC') or 'UTC'
        expire_str = format_local_datetime(sub.expire_at, tz)
        status_text = f'📶 Статус: ✅ Активна\n📅 Действует до: {expire_str}\n'
    else:
        status_text = '📶 Статус: ❌ Нет подписки\n'

    autopay_line = ''
    if has_sub:
        autopay = bool(getattr(user, 'autopay_enabled', False))
        card = _card_last4(user)
        autopay_line = f'🔄 Автопродление: {"✅ вкл" if autopay else "❌ выкл"}'
        if autopay and card:
            autopay_line += f' (•••• {card})'
        autopay_line += '\n'

    text = f'🛡 <b>LiptonVPN</b>\n\n👋 {name}, добро пожаловать!\n\n{status_text}{autopay_line}'
    return text, get_main_menu_keyboard(has_subscription=has_sub, is_admin=is_admin)


# ---------------------------------------------------------------------------
# Главное меню
# ---------------------------------------------------------------------------

async def send_lipton_main_menu(message: types.Message, db: AsyncSession, user, name: str | None = None) -> None:
    """Вызывается из cmd_start когда MAIN_MENU_MODE=lipton; user уже загружен."""
    sub = await get_active_subscription_by_user_id(db, user.id)
    display_name = name or getattr(user, 'first_name', None) or (
        message.from_user.first_name if message.from_user else None
    ) or 'Привет'
    text, keyboard = _build_menu_content(sub, user, display_name)
    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')


async def show_main_menu(callback: types.CallbackQuery, db: AsyncSession, state: FSMContext):
    await state.clear()
    user = await get_user_by_telegram_id(db, callback.from_user.id)
    sub = await get_active_subscription_by_user_id(db, user.id) if user else None
    text, keyboard = _build_menu_content(sub, user, callback.from_user.first_name or 'Привет')
    await callback.answer()
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode='HTML')


# ---------------------------------------------------------------------------
# Тарифы
# ---------------------------------------------------------------------------

async def show_tariffs(callback: types.CallbackQuery):
    await callback.answer()
    text = (
        '📋 <b>Выберите тариф</b>\n\n'
        '🔒 <b>1 месяц</b> — 159 ₽\n'
        '🔒 <b>3 месяца</b> — 450 ₽ <i>(экономия 27 ₽)</i>\n'
        '🔒 <b>12 месяцев</b> — 1 219 ₽ <i>(экономия 689 ₽)</i>\n'
        '🛡 <b>Всегда на связи</b> — 499 ₽\n'
        '   <i>Специальный сервер с обходом российских ограничений</i>\n\n'
        '💳 После выбора тарифа карта будет привязана для автопродления.\n'
        'Отвязать карту можно в разделе Поддержка.'
    )
    try:
        await callback.message.edit_text(text, reply_markup=get_tariffs_keyboard(), parse_mode='HTML')
    except Exception:
        await callback.message.answer(text, reply_markup=get_tariffs_keyboard(), parse_mode='HTML')


# ---------------------------------------------------------------------------
# Покупка тарифа
# ---------------------------------------------------------------------------

async def handle_buy_tariff(callback: types.CallbackQuery, db: AsyncSession, state: FSMContext):
    await callback.answer()

    tariff_key = callback.data.split(':', 1)[1]
    tariff = _TARIFF_CATALOG.get(tariff_key)
    if not tariff:
        await callback.answer('Неизвестный тариф', show_alert=True)
        return

    user = await get_user_by_telegram_id(db, callback.from_user.id)
    if not user:
        await callback.answer('Пользователь не найден', show_alert=True)
        return

    from app.services.payment_service import PaymentService
    payment_service = PaymentService(callback.bot)

    return_url = getattr(settings, 'YOOKASSA_RETURN_URL', None) or f'https://t.me/{settings.BOT_USERNAME}'
    result = await payment_service.create_yookassa_payment(
        db=db,
        user_id=user.id,
        amount_kopeks=tariff['price_kopeks'],
        description=f'LiptonVPN — {tariff["label"]}',
        metadata={
            'user_id': str(user.id),
            'user_telegram_id': str(callback.from_user.id),
            'tariff_key': tariff_key,
            'tariff_label': tariff['label'],
            'tariff_days': str(tariff['days']),
            'type': 'subscription_purchase',
        },
        return_url=return_url,
    )

    if not result or not result.get('confirmation_url'):
        await callback.message.answer(
            '❌ Не удалось создать платёж. Попробуйте позже или обратитесь в поддержку.',
            reply_markup=get_back_keyboard('show_tariffs'),
        )
        return

    await state.update_data(pending_tariff_key=tariff_key, pending_payment_id=result.get('yookassa_payment_id'))

    text = (
        f'💳 <b>Оплата тарифа "{tariff["label"]}"</b>\n\n'
        f'Сумма: <b>{tariff["price_rub"]} ₽</b>\n\n'
        f'Нажмите кнопку для перехода к оплате.\n'
        f'Карта будет привязана автоматически для последующих автосписаний.'
    )
    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_yookassa_pay_keyboard(result['confirmation_url'], tariff_key),
            parse_mode='HTML',
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=get_yookassa_pay_keyboard(result['confirmation_url'], tariff_key),
            parse_mode='HTML',
        )


# ---------------------------------------------------------------------------
# Профиль
# ---------------------------------------------------------------------------

async def show_profile(callback: types.CallbackQuery, db: AsyncSession):
    await callback.answer()

    user = await get_user_by_telegram_id(db, callback.from_user.id)
    if not user:
        await callback.answer('Пользователь не найден', show_alert=True)
        return

    sub = await get_active_subscription_by_user_id(db, user.id)
    card_last4 = _card_last4(user)
    autopay = bool(getattr(user, 'autopay_enabled', False))

    if sub and sub.expire_at:
        expire_str = format_local_datetime(sub.expire_at, getattr(user, 'timezone', 'UTC') or 'UTC')
        sub_line = f'📅 Подписка до: {expire_str}\n'
    else:
        sub_line = '📅 Подписка: не активна\n'

    autopay_line = f'🔄 Автопродление: {"✅ вкл" if autopay else "❌ выкл"}'
    if autopay and card_last4:
        autopay_line += f' (•••• {card_last4})'

    devices_line = ''
    if sub:
        limit = getattr(sub, 'devices_limit', 0) or 0
        devices_line = f'\n📱 Устройств: {limit}'

    text = f'👤 <b>Профиль</b>\n\n{sub_line}{autopay_line}{devices_line}'

    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_profile_keyboard(has_autopay=autopay, card_last4=card_last4),
            parse_mode='HTML',
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=get_profile_keyboard(has_autopay=autopay, card_last4=card_last4),
            parse_mode='HTML',
        )


# ---------------------------------------------------------------------------
# Обход глушилок
# ---------------------------------------------------------------------------

async def show_bypass(callback: types.CallbackQuery):
    await callback.answer()
    text = (
        '🛡 <b>Обход глушилок</b>\n\n'
        'Тариф <b>"Всегда на связи"</b> — специальный сервер с обходом '
        'российских ограничений (DPI, блокировки Роскомнадзора).\n\n'
        '✅ Работает в России без сбоев\n'
        '✅ Стабильное соединение\n'
        '✅ Поддержка всех устройств\n\n'
        '<b>Цена: 499 ₽ / месяц</b>'
    )
    try:
        await callback.message.edit_text(text, reply_markup=get_bypass_keyboard(), parse_mode='HTML')
    except Exception:
        await callback.message.answer(text, reply_markup=get_bypass_keyboard(), parse_mode='HTML')


async def show_bypass_info(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        '🛡 <b>Что такое "Обход глушилок"?</b>\n\n'
        'В России интернет-провайдеры используют системы DPI (глубокая '
        'инспекция пакетов) для блокировки VPN-сервисов.\n\n'
        'Наш специальный сервер использует протоколы, которые маскируются '
        'под обычный HTTPS-трафик — поэтому его невозможно заблокировать '
        'стандартными методами.\n\n'
        '<i>Приложение v2raytun поддерживает этот режим автоматически.</i>',
        reply_markup=get_back_keyboard('show_bypass'),
        parse_mode='HTML',
    )


# ---------------------------------------------------------------------------
# Регистрация
# ---------------------------------------------------------------------------

def register_lipton_menu_handlers(dp: Dispatcher):
    dp.callback_query.register(show_main_menu,  F.data == 'back_to_menu')
    dp.callback_query.register(show_tariffs,    F.data == 'show_tariffs')
    dp.callback_query.register(show_profile,    F.data == 'show_profile')
    dp.callback_query.register(show_bypass,     F.data == 'show_bypass')
    dp.callback_query.register(show_bypass_info, F.data == 'bypass_info')
    dp.callback_query.register(handle_buy_tariff, F.data.startswith('buy_tariff:'))

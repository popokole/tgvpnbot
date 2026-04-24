"""Handler триала и устройств LiptonVPN."""

from __future__ import annotations

import structlog
from aiogram import Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.subscription import get_active_subscription_by_user_id
from app.database.crud.user import get_user_by_telegram_id
from app.keyboards.lipton import (
    PLATFORM_NAMES,
    get_back_keyboard,
    get_device_selection_keyboard,
    get_install_guide_keyboard,
    get_key_issued_keyboard,
    get_my_devices_keyboard,
    get_trial_start_keyboard,
)


logger = structlog.get_logger(__name__)

INSTALL_INSTRUCTIONS = {
    'ios': (
        '📱 <b>Установка на iPhone / iPad</b>\n\n'
        '1. Скачайте <b>v2raytun</b> из App Store\n'
        '2. Откройте → нажмите <b>"+"</b>\n'
        '3. Выберите <b>"Вставить из буфера"</b>\n'
        '4. Вставьте ключ (скопируйте кнопкой выше)\n'
        '5. Включите VPN\n\n'
        '✅ Готово!'
    ),
    'android': (
        '🤖 <b>Установка на Android</b>\n\n'
        '1. Скачайте <b>v2raytun</b> из Google Play\n'
        '2. Откройте → нажмите <b>"+"</b>\n'
        '3. Выберите <b>"Вставить из буфера"</b>\n'
        '4. Вставьте ключ\n'
        '5. Включите VPN\n\n'
        '✅ Готово!'
    ),
    'windows': (
        '💻 <b>Установка на Windows</b>\n\n'
        '1. Скачайте <b>v2rayN</b> с GitHub\n'
        '2. Распакуйте архив и запустите\n'
        '3. Нажмите <b>"Добавить сервер"</b> → <b>"Из буфера"</b>\n'
        '4. Вставьте ключ\n'
        '5. Включите прокси\n\n'
        '✅ Готово!'
    ),
    'macos': (
        '🍎 <b>Установка на macOS</b>\n\n'
        '1. Скачайте <b>V2Box</b> из App Store\n'
        '2. Откройте → нажмите <b>"+"</b> → <b>"Вставить ссылку"</b>\n'
        '3. Вставьте ключ\n'
        '4. Включите VPN\n\n'
        '✅ Готово!'
    ),
    'linux': (
        '🐧 <b>Установка на Linux</b>\n\n'
        '1. Установите <b>v2rayA</b>: `sudo snap install v2raya`\n'
        '2. Запустите: `sudo systemctl start v2raya`\n'
        '3. Откройте браузер: http://localhost:2017\n'
        '4. Импортируйте ключ\n'
        '5. Включите\n\n'
        '✅ Готово!'
    ),
    'android_tv': (
        '📺 <b>Установка на Android TV</b>\n\n'
        '1. Установите <b>v2raytun</b> из Google Play (TV)\n'
        '2. Настройте аналогично Android\n\n'
        '✅ Готово!'
    ),
    'apple_tv': (
        '📺 <b>Установка на Apple TV</b>\n\n'
        '1. Установите <b>v2raytun</b> из App Store (tvOS)\n'
        '2. Настройте аналогично iPhone\n\n'
        '✅ Готово!'
    ),
    'router': (
        '📡 <b>Установка на роутер</b>\n\n'
        'Настройка зависит от прошивки роутера.\n'
        'Поддерживаются: OpenWRT, Keenetic (v3+), Asus Merlin.\n\n'
        'Обратитесь в поддержку — мы поможем настроить конкретную модель.'
    ),
}


# ---------------------------------------------------------------------------
# Триал
# ---------------------------------------------------------------------------

async def show_trial(callback: types.CallbackQuery, db: AsyncSession):
    await callback.answer()

    user = await get_user_by_telegram_id(db, callback.from_user.id)
    if user:
        sub = await get_active_subscription_by_user_id(db, user.id)
        if sub:
            await callback.answer('У вас уже есть активная подписка!', show_alert=True)
            return
        if getattr(user, 'trial_used', False):
            await callback.message.answer(
                '⚠️ <b>Бесплатный период уже использован</b>\n\n'
                'Для продолжения пользования сервисом выберите тариф.',
                reply_markup=get_back_keyboard('show_tariffs'),
                parse_mode='HTML',
            )
            return

    text = (
        '🎁 <b>Бесплатный доступ — 3 дня</b>\n\n'
        'Попробуй LiptonVPN бесплатно!\n\n'
        '✅ Полный доступ на 3 дня\n'
        '✅ До 3 устройств\n'
        '✅ Обход блокировок\n\n'
        '<i>Карта не требуется. После окончания триала подписка не продлевается автоматически.</i>'
    )
    try:
        await callback.message.edit_text(text, reply_markup=get_trial_start_keyboard(), parse_mode='HTML')
    except Exception:
        await callback.message.answer(text, reply_markup=get_trial_start_keyboard(), parse_mode='HTML')


async def trial_get_key(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(flow='trial')
    text = '📱 <b>На каком устройстве настроим?</b>\n\nВыберите платформу:'
    try:
        await callback.message.edit_text(text, reply_markup=get_device_selection_keyboard(), parse_mode='HTML')
    except Exception:
        await callback.message.answer(text, reply_markup=get_device_selection_keyboard(), parse_mode='HTML')


# ---------------------------------------------------------------------------
# Мои устройства
# ---------------------------------------------------------------------------

async def show_devices(callback: types.CallbackQuery, db: AsyncSession):
    await callback.answer()

    user = await get_user_by_telegram_id(db, callback.from_user.id)
    sub = await get_active_subscription_by_user_id(db, user.id) if user else None

    if sub:
        text = (
            '📱 <b>Мои устройства</b>\n\n'
            'Здесь отображаются устройства, подключённые к VPN.\n'
            'Данные синхронизируются с панелью управления.'
        )
    else:
        text = (
            '📱 <b>Мои устройства</b>\n\n'
            'У вас нет активной подписки.\n'
            'Выберите тариф или воспользуйтесь бесплатным периодом.'
        )

    try:
        await callback.message.edit_text(
            text, reply_markup=get_my_devices_keyboard(has_subscription=bool(sub)), parse_mode='HTML'
        )
    except Exception:
        await callback.message.answer(
            text, reply_markup=get_my_devices_keyboard(has_subscription=bool(sub)), parse_mode='HTML'
        )


# ---------------------------------------------------------------------------
# Выбор устройства (платформы)
# ---------------------------------------------------------------------------

async def handle_device_selection(callback: types.CallbackQuery, db: AsyncSession, state: FSMContext):
    await callback.answer()
    platform = callback.data.split(':', 1)[1]
    platform_name = PLATFORM_NAMES.get(platform, platform)

    state_data = await state.get_data()
    if state_data.get('flow') == 'trial':
        await _activate_trial_and_give_key(callback, db, state, platform, platform_name)
    else:
        await _give_key_for_platform(callback, db, platform, platform_name)


async def _activate_trial_and_give_key(
    callback: types.CallbackQuery,
    db: AsyncSession,
    state: FSMContext,
    platform: str,
    platform_name: str,
):
    user = await get_user_by_telegram_id(db, callback.from_user.id)
    if not user:
        await callback.answer('Пользователь не найден', show_alert=True)
        return

    try:
        from app.services.trial_activation_service import TrialActivationService
        result = await TrialActivationService().activate_trial(db, user_id=user.id)
        if not result or not result.get('success'):
            error_msg = result.get('error_message', 'Ошибка активации') if result else 'Ошибка активации'
            await callback.message.answer(f'❌ {error_msg}', reply_markup=get_back_keyboard('back_to_menu'))
            return
        vpn_key = result.get('vless_link') or result.get('subscription_link', '')
    except Exception as e:
        logger.error('Trial activation error', error=e)
        await callback.message.answer(
            '❌ Не удалось активировать триал. Обратитесь в поддержку.',
            reply_markup=get_back_keyboard('show_support'),
        )
        return

    await state.update_data(vpn_key=vpn_key, platform=platform)
    await callback.message.answer(
        f'✅ <b>Бесплатный доступ активирован!</b>\n\n'
        f'Платформа: {platform_name}\n'
        f'Срок: 3 дня\n\n'
        f'Ваш VPN-ключ:\n<code>{vpn_key}</code>\n\n'
        f'Скопируйте ключ и вставьте в приложение v2raytun.',
        reply_markup=get_key_issued_keyboard(platform),
        parse_mode='HTML',
    )


async def _give_key_for_platform(
    callback: types.CallbackQuery,
    db: AsyncSession,
    platform: str,
    platform_name: str,
):
    user = await get_user_by_telegram_id(db, callback.from_user.id)
    if not user:
        await callback.answer('Пользователь не найден', show_alert=True)
        return

    sub = await get_active_subscription_by_user_id(db, user.id)
    if not sub:
        await callback.message.answer(
            '⚠️ У вас нет активной подписки.',
            reply_markup=get_back_keyboard('show_tariffs'),
        )
        return

    vpn_key = getattr(sub, 'vless_link', None) or getattr(sub, 'subscription_link', '')
    await callback.message.answer(
        f'✅ <b>Ключ для {platform_name}</b>\n\n'
        f'<code>{vpn_key}</code>\n\n'
        f'Скопируйте ключ и вставьте в приложение v2raytun.',
        reply_markup=get_key_issued_keyboard(platform),
        parse_mode='HTML',
    )


# ---------------------------------------------------------------------------
# Инструкции по установке
# ---------------------------------------------------------------------------

async def show_install_guide(callback: types.CallbackQuery):
    await callback.answer()
    platform = callback.data.split(':', 1)[1]
    instruction = INSTALL_INSTRUCTIONS.get(platform, 'Инструкция в разработке.')
    await callback.message.answer(
        instruction,
        reply_markup=get_install_guide_keyboard(platform),
        parse_mode='HTML',
    )


async def handle_add_device(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(flow='key')
    text = '📱 <b>Добавить устройство</b>\n\nВыберите платформу:'
    try:
        await callback.message.edit_text(text, reply_markup=get_device_selection_keyboard(), parse_mode='HTML')
    except Exception:
        await callback.message.answer(text, reply_markup=get_device_selection_keyboard(), parse_mode='HTML')


async def refresh_devices(callback: types.CallbackQuery, db: AsyncSession):
    await callback.answer('Обновлено', show_alert=False)
    await show_devices(callback, db)


# ---------------------------------------------------------------------------
# Регистрация
# ---------------------------------------------------------------------------

def register_lipton_trial_handlers(dp: Dispatcher):
    dp.callback_query.register(show_trial,             F.data == 'trial_start')
    dp.callback_query.register(trial_get_key,          F.data == 'trial_get_key')
    dp.callback_query.register(show_devices,           F.data == 'show_devices')
    dp.callback_query.register(handle_device_selection, F.data.startswith('device:'))
    dp.callback_query.register(show_install_guide,     F.data.startswith('install_guide:'))
    dp.callback_query.register(handle_add_device,      F.data == 'add_device')
    dp.callback_query.register(refresh_devices,        F.data == 'refresh_devices')

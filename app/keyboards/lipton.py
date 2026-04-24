"""Клавиатуры LiptonVPN."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu_keyboard(has_subscription: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    if not has_subscription:
        buttons.append([
            InlineKeyboardButton(
                text='🎁 Попробовать 3 дня бесплатно',
                callback_data='trial_start',
                style='success',
            )
        ])
    buttons.extend([
        [InlineKeyboardButton(text='📋 Тарифы',         callback_data='show_tariffs',  style='primary')],
        [InlineKeyboardButton(text='👤 Профиль',        callback_data='show_profile')],
        [InlineKeyboardButton(text='📱 Мои устройства', callback_data='show_devices')],
        [InlineKeyboardButton(text='🛡 Обход глушилок', callback_data='show_bypass')],
        [InlineKeyboardButton(text='💬 Поддержка',      callback_data='show_support')],
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_tariffs_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='1 месяц — 159 ₽',          callback_data='buy_tariff:1m',     style='primary')],
        [InlineKeyboardButton(text='3 месяца — 450 ₽',         callback_data='buy_tariff:3m',     style='primary')],
        [InlineKeyboardButton(text='12 месяцев — 1 219 ₽',     callback_data='buy_tariff:12m',    style='primary')],
        [InlineKeyboardButton(text='🛡 Всегда на связи — 499 ₽', callback_data='buy_tariff:always', style='success')],
        [InlineKeyboardButton(text='◀️ Назад',                  callback_data='back_to_menu')],
    ])


def get_yookassa_pay_keyboard(payment_url: str, tariff_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='💳 Перейти к оплате',  url=payment_url,                              style='success')],
        [InlineKeyboardButton(text='✅ Проверить оплату',  callback_data=f'check_payment:{tariff_key}',  style='primary')],
        [InlineKeyboardButton(text='❌ Отменить',          callback_data='show_tariffs',                 style='danger')],
    ])


def get_profile_keyboard(has_autopay: bool = False, card_last4: str | None = None) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text='🎟 Промокод', callback_data='enter_promo')],
        [InlineKeyboardButton(
            text='🔄 Автопродление: ' + ('вкл ✅' if has_autopay else 'выкл ❌'),
            callback_data='toggle_autopay',
        )],
    ]
    if card_last4:
        buttons.append([InlineKeyboardButton(text=f'💳 Карта •••• {card_last4}', callback_data='manage_card')])
    buttons.append([InlineKeyboardButton(text='◀️ Назад', callback_data='back_to_menu')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


PLATFORMS = [
    ('📱 iPhone / iPad', 'device:ios'),
    ('🤖 Android',       'device:android'),
    ('💻 Windows',       'device:windows'),
    ('🍎 macOS',         'device:macos'),
    ('🐧 Linux',         'device:linux'),
    ('📺 Android TV',    'device:android_tv'),
    ('📺 Apple TV',      'device:apple_tv'),
    ('📡 Роутер',        'device:router'),
]

PLATFORM_NAMES = {
    'ios':        'iPhone / iPad',
    'android':    'Android',
    'windows':    'Windows',
    'macos':      'macOS',
    'linux':      'Linux',
    'android_tv': 'Android TV',
    'apple_tv':   'Apple TV',
    'router':     'Роутер',
}

INSTALL_GUIDES = {
    'ios':        'https://apps.apple.com/app/v2raytun/id6476628951',
    'android':    'https://play.google.com/store/apps/details?id=com.v2raytun.android',
    'windows':    'https://github.com/2dust/v2rayN/releases/latest',
    'macos':      'https://apps.apple.com/app/v2box-v2ray-vpn-client/id6446814690',
    'linux':      'https://v2raya.org/',
    'android_tv': 'https://play.google.com/store/apps/details?id=com.v2raytun.android',
    'apple_tv':   'https://apps.apple.com/app/v2raytun/id6476628951',
    'router':     None,
}


def get_device_selection_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(PLATFORMS), 2):
        row = [InlineKeyboardButton(text=PLATFORMS[i][0], callback_data=PLATFORMS[i][1])]
        if i + 1 < len(PLATFORMS):
            row.append(InlineKeyboardButton(text=PLATFORMS[i + 1][0], callback_data=PLATFORMS[i + 1][1]))
        rows.append(row)
    rows.append([InlineKeyboardButton(text='◀️ Назад', callback_data='back_to_menu')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_key_issued_keyboard(platform: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📲 Как установить v2raytun', callback_data=f'install_guide:{platform}', style='primary')],
        [InlineKeyboardButton(text='🏠 Главное меню',            callback_data='back_to_menu')],
    ])


def get_my_devices_keyboard(has_subscription: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    if has_subscription:
        buttons.append([InlineKeyboardButton(text='➕ Добавить устройство', callback_data='add_device', style='primary')])
    buttons.extend([
        [InlineKeyboardButton(text='🔄 Обновить список', callback_data='refresh_devices')],
        [InlineKeyboardButton(text='◀️ Назад',           callback_data='back_to_menu')],
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_install_guide_keyboard(platform: str) -> InlineKeyboardMarkup:
    buttons = []
    link = INSTALL_GUIDES.get(platform)
    if link:
        buttons.append([InlineKeyboardButton(text='⬇️ Скачать приложение', url=link, style='success')])
    buttons.append([InlineKeyboardButton(text='◀️ Назад', callback_data='show_devices')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_support_keyboard(has_card: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text='ℹ️ О сервисе',        callback_data='support:about')],
        [InlineKeyboardButton(text='❓ Как установить',    callback_data='support:install')],
        [InlineKeyboardButton(text='💡 Предложения',       callback_data='support:suggestions')],
        [InlineKeyboardButton(text='❌ Отменить подписку', callback_data='support:cancel_sub', style='danger')],
    ]
    if has_card:
        buttons.append([InlineKeyboardButton(text='💳 Отвязать карту', callback_data='support:unlink_card', style='danger')])
    buttons.append([InlineKeyboardButton(text='📞 Написать в поддержку', callback_data='support:contact', style='primary')])
    buttons.append([InlineKeyboardButton(text='◀️ Назад', callback_data='back_to_menu')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirm_unlink_card_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='✅ Да, отвязать', callback_data='confirm_unlink_card', style='danger'),
        InlineKeyboardButton(text='❌ Отмена',       callback_data='show_support'),
    ]])


def get_trial_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📱 Выбрать устройство и получить ключ', callback_data='trial_get_key', style='success')],
        [InlineKeyboardButton(text='◀️ Назад', callback_data='back_to_menu')],
    ])


def get_bypass_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🛡 Купить "Всегда на связи" — 499 ₽', callback_data='buy_tariff:always', style='success')],
        [InlineKeyboardButton(text='❓ Что это такое?', callback_data='bypass_info')],
        [InlineKeyboardButton(text='◀️ Назад',          callback_data='back_to_menu')],
    ])


def get_expiry_reminder_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='💳 Продлить сейчас', callback_data='show_tariffs', style='primary')],
    ])


def get_expired_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📋 Выбрать тариф',    callback_data='show_tariffs',  style='primary')],
        [InlineKeyboardButton(text='🎁 Попробовать снова', callback_data='trial_start',   style='success')],
    ])


def get_back_keyboard(callback_data: str = 'back_to_menu') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='◀️ Назад', callback_data=callback_data)],
    ])


def get_confirm_keyboard(
    confirm_callback: str,
    cancel_callback: str = 'back_to_menu',
    confirm_text: str = '✅ Подтвердить',
    cancel_text: str = '❌ Отмена',
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=confirm_text, callback_data=confirm_callback, style='success'),
        InlineKeyboardButton(text=cancel_text,  callback_data=cancel_callback),
    ]])

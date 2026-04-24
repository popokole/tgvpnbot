"""Webhook-роутер платежей — только YooKassa."""

from __future__ import annotations

import json

import structlog
from aiogram import Bot
from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.external import yookassa_webhook as yookassa_webhook_module
from app.services.payment_service import PaymentService


logger = structlog.get_logger(__name__)


async def _process_yookassa_webhook(
    payment_service: PaymentService,
    webhook_data: dict,
) -> bool:
    from app.database.database import get_db

    db_gen = get_db()
    try:
        db = await db_gen.__anext__()
        return await payment_service.process_yookassa_webhook(db, webhook_data)
    finally:
        try:
            await db_gen.__anext__()
        except StopAsyncIteration:
            pass


def create_payment_router(bot: Bot, payment_service: PaymentService) -> APIRouter | None:
    if not settings.is_yookassa_enabled():
        logger.warning('YooKassa не настроен — webhook-роутер не зарегистрирован')
        return None

    router = APIRouter()

    @router.options(settings.YOOKASSA_WEBHOOK_PATH)
    async def yookassa_options() -> Response:
        return Response(
            status_code=status.HTTP_200_OK,
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, X-YooKassa-Signature, Signature',
            },
        )

    @router.get(settings.YOOKASSA_WEBHOOK_PATH)
    async def yookassa_health() -> JSONResponse:
        return JSONResponse({'status': 'ok', 'service': 'yookassa_webhook', 'enabled': True})

    @router.post(settings.YOOKASSA_WEBHOOK_PATH)
    async def yookassa_webhook(request: Request) -> JSONResponse:
        header_ip_candidates = yookassa_webhook_module.collect_yookassa_ip_candidates(
            request.headers.get('X-Forwarded-For'),
            request.headers.get('X-Real-IP'),
            request.headers.get('Cf-Connecting-Ip'),
        )
        remote_ip = request.client.host if request.client else None
        client_ip = yookassa_webhook_module.resolve_yookassa_ip(header_ip_candidates, remote=remote_ip)

        if client_ip is None:
            return JSONResponse({'status': 'error', 'reason': 'unknown_ip'}, status_code=status.HTTP_403_FORBIDDEN)

        if not yookassa_webhook_module.is_yookassa_ip_allowed(client_ip):
            return JSONResponse({'status': 'error', 'reason': 'forbidden_ip'}, status_code=status.HTTP_403_FORBIDDEN)

        body_bytes = await request.body()
        if not body_bytes:
            return JSONResponse({'status': 'error', 'reason': 'empty_body'}, status_code=status.HTTP_400_BAD_REQUEST)

        try:
            webhook_data = json.loads(body_bytes.decode('utf-8'))
        except json.JSONDecodeError:
            return JSONResponse(
                {'status': 'error', 'reason': 'invalid_json'}, status_code=status.HTTP_400_BAD_REQUEST
            )

        event_type = webhook_data.get('event')
        if not event_type:
            return JSONResponse(
                {'status': 'error', 'reason': 'missing_event'}, status_code=status.HTTP_400_BAD_REQUEST
            )

        if event_type not in {'payment.succeeded', 'payment.waiting_for_capture', 'payment.canceled'}:
            return JSONResponse({'status': 'ok', 'ignored': event_type})

        try:
            success = await _process_yookassa_webhook(payment_service, webhook_data)
            if success:
                return JSONResponse({'status': 'ok'})

            payment_id = webhook_data.get('object', {}).get('id', 'unknown')
            logger.error('YooKassa webhook processing failed', payment_id=payment_id)
            return JSONResponse(
                {'status': 'error', 'reason': 'processing_failed'},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            logger.exception('YooKassa webhook processing error', e=e)
            return JSONResponse(
                {'status': 'error', 'reason': 'processing_failed'},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @router.get('/health/payment-webhooks')
    async def payment_webhooks_health() -> JSONResponse:
        return JSONResponse({'status': 'ok', 'yookassa_enabled': settings.is_yookassa_enabled()})

    return router

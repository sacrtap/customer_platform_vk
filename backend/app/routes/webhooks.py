"""
P6-8: 客户确认 Webhook 接口
接收外部系统回调，处理客户确认结算单操作
"""

import hmac
import hashlib
import logging
from datetime import datetime, timedelta
from sanic import Blueprint
from sanic.response import json
from sqlalchemy import select

from ..models.invoice import Invoice, InvoiceStatus
from ..models.webhooks import WebhookSignature
from ..config import settings

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint("webhooks", url_prefix="/api/v1/webhooks")


# Webhook 时间戳窗口配置（秒）
WEBHOOK_TIMESTAMP_WINDOW = 300  # 5 分钟


def verify_timestamp_window(
    timestamp: str, window_seconds: int = WEBHOOK_TIMESTAMP_WINDOW
) -> bool:
    """
    验证时间戳是否在有效窗口内

    Args:
        timestamp: ISO 格式时间戳字符串
        window_seconds: 有效时间窗口（秒），默认 5 分钟

    Returns:
        bool: 时间戳是否有效
    """
    try:
        # 解析时间戳（支持带 Z 和不带时区的格式）
        ts_str = timestamp.replace("Z", "+00:00")
        if "+" not in ts_str and ts_str.count("-") == 2:
            # 无时区信息，视为 UTC
            req_time = datetime.fromisoformat(ts_str)
        else:
            req_time = datetime.fromisoformat(ts_str)

        # 计算时间差
        now = datetime.utcnow()
        time_diff = abs((now - req_time).total_seconds())

        if time_diff > window_seconds:
            logger.warning(
                f"Webhook 时间戳过期 | 请求时间：{req_time} | 当前时间：{now} | "
                f"时间差：{time_diff}s | 允许窗口：{window_seconds}s"
            )
            return False

        return True
    except ValueError as e:
        logger.warning(f"Webhook 时间戳格式无效：{timestamp}, 错误：{str(e)}")
        return False
    except Exception as e:
        logger.error(f"时间戳验证异常：{str(e)}")
        return False


async def check_signature_not_used(db_session, signature: str) -> bool:
    """
    检查签名是否未被使用（防止重放攻击）

    Args:
        db_session: 数据库会话
        signature: 请求签名

    Returns:
        bool: True 表示签名未被使用（安全），False 表示已使用（重放攻击）
    """
    try:
        result = await db_session.execute(
            select(WebhookSignature).where(
                WebhookSignature.signature == signature,
                WebhookSignature.deleted_at.is_(None),
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.warning(
                f"⚠️ Webhook 重放攻击检测 | 签名已使用 | "
                f"签名：{signature[:16]}... | "
                f"首次使用时间：{existing.timestamp}"
            )
            return False  # 签名已使用，拒绝请求

        return True  # 签名未使用，安全
    except Exception as e:
        logger.error(f"签名去重检查异常：{str(e)}")
        return False


async def record_webhook_signature(
    db_session, signature: str, timestamp: str, endpoint: str
):
    """
    记录已使用的 Webhook 签名

    Args:
        db_session: 数据库会话
        signature: 请求签名
        timestamp: 请求时间戳
        endpoint: Webhook 端点路径
    """
    try:
        # 解析时间戳
        ts_str = timestamp.replace("Z", "+00:00")
        try:
            req_time = datetime.fromisoformat(ts_str)
        except ValueError:
            req_time = datetime.utcnow()

        webhook_sig = WebhookSignature(
            signature=signature,
            timestamp=req_time,
            endpoint=endpoint,
            is_consumed=False,
        )
        db_session.add(webhook_sig)
        await db_session.commit()

        logger.debug(f"✅ Webhook 签名已记录 | 端点：{endpoint}")
    except Exception as e:
        logger.error(f"记录 Webhook 签名失败：{str(e)}")
        # 不抛出异常，避免影响主流程


def verify_webhook_signature(payload: bytes, signature: str, timestamp: str) -> bool:
    """
    验证 Webhook 签名

    签名算法：HMAC-SHA256(timestamp + payload, secret)

    Args:
        payload: 请求体原始字节
        signature: 请求头中的签名
        timestamp: 请求头中的时间戳

    Returns:
        bool: 签名是否有效
    """
    try:
        secret = settings.webhook_secret.encode("utf-8")
        message = f"{timestamp}{payload.decode('utf-8')}".encode("utf-8")

        expected_signature = hmac.new(secret, message, hashlib.sha256).hexdigest()

        return hmac.compare_digest(signature, expected_signature)
    except Exception as e:
        logger.error(f"签名验证异常：{str(e)}")
        return False


@webhooks_bp.post("/invoice-confirmation")
async def invoice_confirmation(request):
    """
    结算单客户确认回调

    外部系统调用此接口通知客户已确认结算单

    Request Headers:
        X-Webhook-Signature: HMAC-SHA256 签名
        X-Webhook-Timestamp: 时间戳

    Request Body:
        {
            "invoice_no": "INV-2024-001",
            "customer_id": 123,
            "confirmed_at": "2024-01-15T10:30:00Z",
            "confirmation_method": "email",  // email/sms/system
            "remarks": "客户已确认"
        }

    Response:
        {
            "code": 0,
            "message": "success",
            "data": {
                "invoice_id": 1,
                "status": "customer_confirmed"
            }
        }
    """
    try:
        # 获取签名和时间戳
        signature = request.headers.get("X-Webhook-Signature")
        timestamp = request.headers.get("X-Webhook-Timestamp")

        if not signature or not timestamp:
            logger.warning("Webhook 请求缺少签名或时间戳")
            return json(
                {"code": 401, "message": "缺少签名或时间戳", "data": None}, status=401
            )

        # 1. 验证时间戳窗口（防止旧请求重放）
        if not verify_timestamp_window(timestamp):
            return json(
                {"code": 403, "message": "请求时间戳过期", "data": None}, status=403
            )

        # 2. 检查签名是否已被使用（防止重放攻击）
        if not await check_signature_not_used(db_session, signature):
            return json(
                {"code": 403, "message": "签名已使用，拒绝重放请求", "data": None},
                status=403,
            )

        # 3. 验证签名
        if not verify_webhook_signature(request.body, signature, timestamp):
            logger.warning("Webhook 签名验证失败")
            return json(
                {"code": 403, "message": "签名验证失败", "data": None}, status=403
            )

        # 解析请求体
        data = request.json
        invoice_no = data.get("invoice_no")
        customer_id = data.get("customer_id")
        confirmed_at = data.get("confirmed_at")
        confirmation_method = data.get("confirmation_method", "system")
        remarks = data.get("remarks", "")

        if not invoice_no:
            return json(
                {"code": 400, "message": "缺少结算单号", "data": None}, status=400
            )

        # 获取数据库会话
        db_session = request.ctx.db_session

        # 查找结算单
        result = await db_session.execute(
            select(Invoice).where(
                Invoice.invoice_no == invoice_no, Invoice.deleted_at.is_(None)
            )
        )
        invoice = result.scalar_one_or_none()

        if not invoice:
            logger.warning(f"结算单不存在：{invoice_no}")
            return json(
                {"code": 404, "message": f"结算单不存在：{invoice_no}", "data": None},
                status=404,
            )

        # 检查结算单状态
        if invoice.status != InvoiceStatus.PENDING_CUSTOMER:
            logger.warning(
                f"结算单状态不正确：{invoice_no}, 当前状态：{invoice.status}"
            )
            return json(
                {
                    "code": 400,
                    "message": f"结算单状态不正确，当前状态：{invoice.status.value}",
                    "data": None,
                },
                status=400,
            )

        # 更新结算单状态
        invoice.status = InvoiceStatus.CUSTOMER_CONFIRMED
        invoice.customer_confirmed_at = datetime.utcnow()
        invoice.confirmation_method = confirmation_method
        invoice.confirmation_remarks = remarks

        # 记录 Webhook 签名（防止重放）
        await record_webhook_signature(
            db_session, signature, timestamp, "/invoice-confirmation"
        )

        await db_session.commit()

        logger.info(
            f"✅ 结算单客户确认成功 | "
            f"单号：{invoice_no} | "
            f"客户 ID: {customer_id} | "
            f"确认方式：{confirmation_method}"
        )

        return json(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "invoice_id": invoice.id,
                    "invoice_no": invoice.invoice_no,
                    "status": invoice.status.value,
                    "confirmed_at": invoice.customer_confirmed_at.isoformat(),
                },
            }
        )

    except Exception as e:
        logger.error(f"❌ 结算单确认回调处理失败：{str(e)}")
        return json(
            {"code": 500, "message": f"处理失败：{str(e)}", "data": None}, status=500
        )


@webhooks_bp.post("/payment-notify")
async def payment_notify(request):
    """
    付款通知回调

    外部支付系统调用此接口通知客户已付款

    Request Headers:
        X-Webhook-Signature: HMAC-SHA256 签名
        X-Webhook-Timestamp: 时间戳

    Request Body:
        {
            "invoice_no": "INV-2024-001",
            "payment_amount": 1000.00,
            "payment_method": "bank_transfer",
            "payment_time": "2024-01-15T10:30:00Z",
            "transaction_id": "TXN123456"
        }
    """
    try:
        # 获取签名和时间戳
        signature = request.headers.get("X-Webhook-Signature")
        timestamp = request.headers.get("X-Webhook-Timestamp")

        if not signature or not timestamp:
            return json(
                {"code": 401, "message": "缺少签名或时间戳", "data": None}, status=401
            )

        # 获取数据库会话
        db_session = request.ctx.db_session

        # 1. 验证时间戳窗口（防止旧请求重放）
        if not verify_timestamp_window(timestamp):
            return json(
                {"code": 403, "message": "请求时间戳过期", "data": None}, status=403
            )

        # 2. 检查签名是否已被使用（防止重放攻击）
        if not await check_signature_not_used(db_session, signature):
            return json(
                {"code": 403, "message": "签名已使用，拒绝重放请求", "data": None},
                status=403,
            )

        # 3. 验证签名
        if not verify_webhook_signature(request.body, signature, timestamp):
            return json(
                {"code": 403, "message": "签名验证失败", "data": None}, status=403
            )

        # 解析请求体
        data = request.json
        invoice_no = data.get("invoice_no")
        payment_amount = data.get("payment_amount")
        payment_method = data.get("payment_method")
        payment_time = data.get("payment_time")
        transaction_id = data.get("transaction_id")

        if not invoice_no or not payment_amount:
            return json(
                {"code": 400, "message": "缺少必要参数", "data": None}, status=400
            )

        # 查找结算单
        result = await db_session.execute(
            select(Invoice).where(
                Invoice.invoice_no == invoice_no, Invoice.deleted_at.is_(None)
            )
        )
        invoice = result.scalar_one_or_none()

        if not invoice:
            return json(
                {"code": 404, "message": f"结算单不存在：{invoice_no}", "data": None},
                status=404,
            )

        # 检查结算单状态
        if invoice.status not in [
            InvoiceStatus.CUSTOMER_CONFIRMED,
            InvoiceStatus.PENDING_CUSTOMER,
        ]:
            return json(
                {
                    "code": 400,
                    "message": f"结算单状态不正确，当前状态：{invoice.status.value}",
                    "data": None,
                },
                status=400,
            )

        # 验证付款金额
        if abs(payment_amount - invoice.final_amount) > 0.01:
            logger.warning(
                f"付款金额不匹配 | 结算单：{invoice.final_amount} | 实付：{payment_amount}"
            )
            # 金额不匹配时，记录但不拒绝，由财务人工核对

        # 更新结算单状态
        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = datetime.utcnow()
        invoice.payment_method = payment_method
        invoice.transaction_id = transaction_id

        # 记录 Webhook 签名（防止重放）
        await record_webhook_signature(
            db_session, signature, timestamp, "/payment-notify"
        )

        await db_session.commit()

        logger.info(
            f"✅ 付款通知处理成功 | "
            f"单号：{invoice_no} | "
            f"金额：{payment_amount} | "
            f"交易 ID: {transaction_id}"
        )

        return json(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "invoice_id": invoice.id,
                    "invoice_no": invoice.invoice_no,
                    "status": invoice.status.value,
                },
            }
        )

    except Exception as e:
        logger.error(f"❌ 付款通知处理失败：{str(e)}")
        return json(
            {"code": 500, "message": f"处理失败：{str(e)}", "data": None}, status=500
        )

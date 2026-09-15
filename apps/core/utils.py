"""公共工具函数：流水号生成、加密解密、签名验签。"""
import uuid
import time
import random
from datetime import date
from django.conf import settings

_cipher = None
_Fernet = None


def _get_fernet():
    global _Fernet
    if _Fernet is None:
        from cryptography.fernet import Fernet as _F
        _Fernet = _F
    return _Fernet


def _get_cipher():
    global _cipher
    if _cipher is None:
        key = settings.FIELD_ENCRYPTION_KEY
        _cipher = _get_fernet()(key.encode() if isinstance(key, str) else key)
    return _cipher


# ── 流水号生成 ──────────────────────────────────────────────

def generate_order_no(prefix: str = "P") -> str:
    """生成平台订单号：P + YYYYMMDDHHmmss + 微秒 + 随机数。

    示例: P20260706153045123456001
    """
    import datetime
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d%H%M%S")
    microsecond = str(now.microsecond).zfill(6)
    random_part = str(random.randint(100000, 999999))
    return f"{prefix}{timestamp}{microsecond}{random_part}"


def generate_uin() -> str:
    """生成汇款唯一识别号（Unique Identification Number）。

    用户汇款时将此号填入附言，平台通过它自动匹配订单。
    """
    return f"UIN{int(time.time() * 1000)}{random.randint(1000, 9999)}"


def generate_batch_no(prefix: str = "B") -> str:
    """生成批次号。"""
    from datetime import datetime
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d%H%M%S")
    return f"{prefix}{timestamp}{random.randint(1000, 9999)}"


def generate_reconciliation_batch_no() -> str:
    """生成对账批次号。"""
    today = date.today().strftime("%Y%m%d")
    return f"RECON{today}{random.randint(100, 999)}"


# ── 字段加密 ────────────────────────────────────────────────

def encrypt_field(plaintext: str) -> str:
    """加密敏感字段（身份证号、银行账号等）。

    返回 base64 编码的密文，可直接存入数据库。
    """
    if not plaintext:
        return plaintext
    return _get_cipher().encrypt(plaintext.encode()).decode()


def decrypt_field(ciphertext: str) -> str:
    """解密敏感字段。

    兼容资料初审写入的明文：密文无效时原样返回，避免运营审核页 500。
    """
    if not ciphertext:
        return ciphertext
    try:
        return _get_cipher().decrypt(ciphertext.encode()).decode()
    except Exception:
        return ciphertext


# ── 签名工具 ────────────────────────────────────────────────

def sign_params(params: dict, secret: str) -> str:
    """对请求参数做 HMAC-SHA256 签名。

    签名规则：按 key 字母序排序 → 拼接 key=value → 追加 secret → HMAC-SHA256
    """
    import hmac
    import hashlib

    sorted_keys = sorted(params.keys())
    sign_str = "&".join(f"{k}={params[k]}" for k in sorted_keys if params[k] is not None)
    sign_str += f"&key={secret}"

    return hmac.new(
        secret.encode(), sign_str.encode(), hashlib.sha256
    ).hexdigest()


def verify_signature(params: dict, signature: str, secret: str) -> bool:
    """验签。"""
    import hmac
    expected = sign_params(params, secret)
    return hmac.compare_digest(expected, signature)


# ── 幂等 Key ────────────────────────────────────────────────

def generate_idempotency_key(prefix: str = "") -> str:
    """生成幂等键。"""
    return f"{prefix}{uuid.uuid4().hex}" if prefix else uuid.uuid4().hex

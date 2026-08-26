"""PRN 生成服务 — 可配置前缀/长度/校验位，保证全局唯一与幂等。"""
import random

from django.db import transaction

from apps.core.exceptions import BusinessException, ErrorCode
from apps.payment.models import PaymentOrder, PRNConfig


def _random_body(length: int, charset: str) -> str:
    """按字符集生成指定位数的随机主体。"""
    if charset == PRNConfig.Charset.ALNUM:
        import string
        alphabet = string.digits + string.ascii_uppercase
    else:
        alphabet = "0123456789"
    return "".join(random.choices(alphabet, k=length))


def _check_digit(body: str) -> str:
    """简单校验位：主体中数字位之和 mod 10。"""
    digits = [int(ch) for ch in body if ch.isdigit()]
    return str(sum(digits) % 10)


@transaction.atomic
def generate_prn(config: PRNConfig = None) -> str:
    """按配置生成全局唯一的 PRN 码。

    组成: prefix + 主体(随机) [+ 校验位]。生成即查询占用，保证唯一与幂等。
    """
    config = config or PRNConfig.get_config()
    max_len = PaymentOrder._meta.get_field("prn_code").max_length
    for _ in range(100):
        body = _random_body(config.length, config.charset)
        code = config.prefix + body
        if config.use_check_digit:
            code += _check_digit(body)
        if len(code) > max_len:
            continue
        if not PaymentOrder.objects.filter(prn_code=code).exists():
            return code
    raise BusinessException(ErrorCode.INTERNAL_ERROR, "PRN code generation failed, please retry")

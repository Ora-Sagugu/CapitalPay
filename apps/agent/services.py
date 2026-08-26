"""Agent services"""
import random
from datetime import datetime
from apps.core.exceptions import BusinessException, ErrorCode


def generate_agent_no():
    """生成代理编号 AG + 时间戳 + 随机数"""
    now = datetime.now()
    rand_part = random.randint(10000, 99999)
    return f"AG{now.strftime('%Y%m%d%H%M%S')}{rand_part}"


def generate_commission_no():
    """生成佣金单号 CM + 时间戳 + 随机数"""
    now = datetime.now()
    rand_part = random.randint(10000, 99999)
    return f"CM{now.strftime('%Y%m%d%H%M%S')}{rand_part}"

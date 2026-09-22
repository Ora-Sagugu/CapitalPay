# Generated manually for remittance funding methods

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0014_peer_merchant_agent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentorder',
            name='pay_method',
            field=models.CharField(
                choices=[
                    ('ONLINE_BANK', '银行网银支付'),
                    ('AUTHORIZED', '账户授权支付'),
                    ('WIRE_TRANSFER', '转款汇款'),
                    ('WALLET', '钱包支付'),
                    ('CARD', '银行卡支付'),
                ],
                max_length=32,
                verbose_name='支付方式',
            ),
        ),
    ]

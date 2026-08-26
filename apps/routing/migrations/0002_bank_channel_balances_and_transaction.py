# Generated manually for bank management features

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('routing', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='bankchannel',
            name='country',
            field=models.CharField(default='', max_length=50, verbose_name='国家'),
        ),
        migrations.AddField(
            model_name='bankchannel',
            name='usd_balance',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=18, verbose_name='USD余额'),
        ),
        migrations.AddField(
            model_name='bankchannel',
            name='hkd_balance',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=18, verbose_name='HKD余额'),
        ),
        migrations.AddField(
            model_name='bankchannel',
            name='cny_balance',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=18, verbose_name='CNY余额'),
        ),
        migrations.CreateModel(
            name='BankTransaction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('txn_date', models.DateTimeField(db_index=True, verbose_name='交易日期')),
                ('prn', models.CharField(db_index=True, max_length=32, verbose_name='PRN')),
                ('beneficiary_name', models.CharField(max_length=128, verbose_name='收款人姓名')),
                ('amount', models.DecimalField(decimal_places=2, default=0, max_digits=18, verbose_name='金额')),
                ('currency', models.CharField(default='USD', max_length=3, verbose_name='币种')),
                ('fee', models.DecimalField(decimal_places=2, default=0, max_digits=18, verbose_name='手续费')),
                ('balance', models.DecimalField(decimal_places=2, default=0, max_digits=18, verbose_name='余额')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('bank', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='routing.bankchannel', verbose_name='银行')),
            ],
            options={
                'verbose_name': '银行汇款记录',
                'verbose_name_plural': '银行汇款记录',
                'db_table': 'bank_transaction',
                'ordering': ['-txn_date'],
            },
        ),
    ]

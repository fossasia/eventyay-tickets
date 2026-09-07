from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0067_user_profile_picture_user_profile_picture_thumbnail_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoicevoucher',
            name='status',
            field=models.CharField(
                choices=[('active', 'Active'), ('disabled', 'Disabled'), ('draft', 'Draft')],
                db_index=True,
                default='active',
                max_length=20,
                verbose_name='Status',
            ),
        ),
        migrations.AddField(
            model_name='invoicevoucher',
            name='comment',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Optional note for internal reference. Not shown publicly.',
                verbose_name='Internal note',
            ),
        ),
        migrations.AddField(
            model_name='invoicevoucher',
            name='allow_partial_usage',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'If enabled, the voucher can be used multiple times until the budget '
                    'or redemption limit is reached.'
                ),
                verbose_name='Allow partial usage',
            ),
        ),
        migrations.AlterModelOptions(
            name='invoicevoucher',
            options={
                'ordering': ('-updated_at',),
                'verbose_name': 'Platform Fee Voucher',
                'verbose_name_plural': 'Platform Fee Vouchers',
            },
        ),
    ]

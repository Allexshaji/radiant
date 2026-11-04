from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_user_per_day_salary'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='per_day_salary',
        ),
        migrations.AddField(
            model_name='user',
            name='monthly_salary',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Monthly salary set by the admin', max_digits=10, null=True),
        ),
    ]

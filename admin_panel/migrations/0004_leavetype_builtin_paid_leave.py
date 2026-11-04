from django.db import migrations, models


def set_up_leave_types(apps, schema_editor):
    LeaveType = apps.get_model('admin_panel', 'LeaveType')

    # Leave types that already exist were created by admins (for example sick leave).
    # They are unpaid until an admin ticks Paid for them.
    LeaveType.objects.update(is_paid=False)

    # The built-in paid leave type is always there, so admins never have to create it.
    paid_leave, created = LeaveType.objects.get_or_create(
        name='Paid Leave',
        defaults={
            'description': 'Built-in paid leave. Not deducted from salary.',
            'days_per_year': 12,
            'is_active': True,
            'is_paid': True,
            'is_builtin': True,
        },
    )
    if not created:
        paid_leave.is_builtin = True
        paid_leave.is_paid = True
        paid_leave.save(update_fields=['is_builtin', 'is_paid'])


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0003_leavetype_is_paid'),
    ]

    operations = [
        migrations.AddField(
            model_name='leavetype',
            name='is_builtin',
            field=models.BooleanField(default=False, editable=False, help_text='Built-in leave types cannot be deleted'),
        ),
        migrations.AlterField(
            model_name='leavetype',
            name='is_paid',
            field=models.BooleanField(default=False, help_text='Paid leave is not deducted from salary'),
        ),
        migrations.RunPython(set_up_leave_types, migrations.RunPython.noop),
    ]

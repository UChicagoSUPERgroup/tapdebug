# Generated by Django 2.2 on 2021-10-26 22:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0012_auto_20210728_0500'),
    ]

    operations = [
        migrations.AddField(
            model_name='scenariopage',
            name='isimpfeedback',
            field=models.BooleanField(default=False),
        ),
    ]

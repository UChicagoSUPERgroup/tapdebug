# Generated by Django 2.2 on 2021-07-27 02:24

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0008_auto_20210721_0353'),
    ]

    operations = [
        migrations.AlterField(
            model_name='location',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='backend.User'),
        ),
    ]
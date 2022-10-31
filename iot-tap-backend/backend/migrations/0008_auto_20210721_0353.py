# Generated by Django 2.2 on 2021-07-21 03:53

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0007_devicemonitor'),
    ]

    operations = [
        migrations.CreateModel(
            name='Scenario',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stage', models.TextField(choices=[('i', 'Initialization'), ('t', 'Tutorial'), ('s', 'Survey')], default='i')),
                ('task', models.TextField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.TextField(max_length=128, unique=True)),
                ('mode', models.TextField(choices=[('c', 'Control'), ('sf', 'Syn_feedback'), ('nf', 'Nosyn_feedback'), ('sn', 'Syn_nofeedback'), ('nn', 'Nosyn_nofeedback')], default='c', null=True)),
                ('currentscenario', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='backend.Scenario')),
            ],
        ),
        migrations.RemoveField(
            model_name='parvalmapping',
            name='param',
        ),
        migrations.RemoveField(
            model_name='stcapability',
            name='capabilities',
        ),
        migrations.DeleteModel(
            name='User_ICSE19',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='user',
        ),
        migrations.RemoveField(
            model_name='location',
            name='mode',
        ),
        migrations.RemoveField(
            model_name='location',
            name='name',
        ),
        migrations.AddField(
            model_name='location',
            name='is_template',
            field=models.BooleanField(default=False),
        ),
        migrations.DeleteModel(
            name='ParValMapping',
        ),
        migrations.DeleteModel(
            name='STCapability',
        ),
        migrations.DeleteModel(
            name='UserProfile',
        ),
        migrations.AddField(
            model_name='location',
            name='scenario',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='backend.Scenario'),
        ),
        migrations.AddField(
            model_name='location',
            name='user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='backend.User'),
        ),
    ]
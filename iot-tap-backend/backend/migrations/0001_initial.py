# Generated by Django 2.2 on 2021-02-16 00:26

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Action',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField(max_length=128, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Capability',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=30)),
                ('readable', models.BooleanField(default=True)),
                ('writeable', models.BooleanField(default=True)),
                ('statelabel', models.TextField(blank=True, max_length=256, null=True)),
                ('commandlabel', models.TextField(blank=True, max_length=256, null=True)),
                ('eventlabel', models.TextField(blank=True, max_length=256, null=True)),
                ('commandname', models.TextField(blank=True, max_length=64, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Channel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=30)),
                ('icon', models.TextField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Counter',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('typ', models.TextField(choices=[('set', 'Set'), ('range', 'Range'), ('bin', 'Binary'), ('color', 'Color')])),
                ('count', models.IntegerField(default=0)),
                ('automated_count', models.IntegerField(default=0)),
                ('cap', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Capability')),
            ],
        ),
        migrations.CreateModel(
            name='Device',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('public', models.BooleanField(default=False)),
                ('dev_type', models.TextField(choices=[('st', 'smartthings'), ('v', 'virtualdev'), ('h', 'homeio'), ('f', 'fakedev')], default='f')),
                ('name', models.CharField(max_length=128)),
                ('icon', models.TextField(default='highlight', null=True)),
                ('caps', models.ManyToManyField(to='backend.Capability')),
            ],
        ),
        migrations.CreateModel(
            name='ErrorLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('function', models.CharField(blank=True, default='', max_length=64, null=True)),
                ('err', models.TextField(blank=True, default='', null=True)),
                ('created', models.DateTimeField(auto_now=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Location',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(max_length=40, unique=True)),
                ('name', models.CharField(max_length=256)),
                ('users', models.ManyToManyField(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Parameter',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField()),
                ('sysname', models.TextField(null=True)),
                ('is_command', models.NullBooleanField()),
                ('is_main_param', models.NullBooleanField()),
                ('type', models.TextField(choices=[('set', 'Set'), ('range', 'Range'), ('bin', 'Binary'), ('color', 'Color'), ('time', 'Time'), ('duration', 'Duration'), ('input', 'Input'), ('meta', 'Meta')])),
                ('cap', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Capability')),
            ],
        ),
        migrations.CreateModel(
            name='Rule',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lastedit', models.DateTimeField(auto_now=True)),
                ('type', models.CharField(choices=[('es', 'es'), ('ss', 'ss')], max_length=3)),
                ('location', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Location')),
            ],
        ),
        migrations.CreateModel(
            name='User_ICSE19',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=30, null=True, unique=True)),
                ('code', models.TextField(max_length=128)),
                ('mode', models.CharField(choices=[('rules', 'Rule'), ('sp', 'Safety Property')], max_length=5)),
            ],
        ),
        migrations.CreateModel(
            name='BinCounter',
            fields=[
                ('counter_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='backend.Counter')),
                ('val', models.TextField(blank=True)),
            ],
            bases=('backend.counter',),
        ),
        migrations.CreateModel(
            name='BinParam',
            fields=[
                ('parameter_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='backend.Parameter')),
                ('tval', models.TextField()),
                ('fval', models.TextField()),
            ],
            bases=('backend.parameter',),
        ),
        migrations.CreateModel(
            name='ColorCounter',
            fields=[
                ('counter_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='backend.Counter')),
                ('name', models.TextField(blank=True)),
                ('rgb', models.TextField(blank=True)),
            ],
            bases=('backend.counter',),
        ),
        migrations.CreateModel(
            name='ColorParam',
            fields=[
                ('parameter_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='backend.Parameter')),
                ('mode', models.TextField(choices=[('rgb', 'RGB'), ('hsv', 'HSV'), ('hex', 'Hex')])),
            ],
            bases=('backend.parameter',),
        ),
        migrations.CreateModel(
            name='DurationParam',
            fields=[
                ('parameter_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='backend.Parameter')),
                ('comp', models.BooleanField(default=False)),
                ('maxhours', models.IntegerField(default=23, null=True)),
                ('maxmins', models.IntegerField(default=59, null=True)),
                ('maxsecs', models.IntegerField(default=59, null=True)),
            ],
            bases=('backend.parameter',),
        ),
        migrations.CreateModel(
            name='InputParam',
            fields=[
                ('parameter_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='backend.Parameter')),
                ('inputtype', models.TextField(choices=[('int', 'Integer'), ('stxt', 'Short Text'), ('ltxt', 'Long Text'), ('trig', 'Trigger')])),
            ],
            bases=('backend.parameter',),
        ),
        migrations.CreateModel(
            name='MetaParam',
            fields=[
                ('parameter_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='backend.Parameter')),
                ('is_event', models.BooleanField()),
            ],
            bases=('backend.parameter',),
        ),
        migrations.CreateModel(
            name='RangeCounter',
            fields=[
                ('counter_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='backend.Counter')),
                ('min', models.FloatField(default=float("-inf"))),
                ('max', models.FloatField(default=float("inf"))),
                ('representative', models.FloatField()),
            ],
            bases=('backend.counter',),
        ),
        migrations.CreateModel(
            name='RangeParam',
            fields=[
                ('parameter_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='backend.Parameter')),
                ('min', models.IntegerField()),
                ('max', models.IntegerField()),
                ('interval', models.FloatField(default=1.0)),
            ],
            bases=('backend.parameter',),
        ),
        migrations.CreateModel(
            name='SetCounter',
            fields=[
                ('counter_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='backend.Counter')),
                ('val', models.TextField(blank=True)),
            ],
            bases=('backend.counter',),
        ),
        migrations.CreateModel(
            name='SetParam',
            fields=[
                ('parameter_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='backend.Parameter')),
                ('numopts', models.IntegerField(default=0)),
            ],
            bases=('backend.parameter',),
        ),
        migrations.CreateModel(
            name='TimeParam',
            fields=[
                ('parameter_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='backend.Parameter')),
                ('mode', models.TextField(choices=[('24', '24-hour'), ('12', '12-hour')])),
            ],
            bases=('backend.parameter',),
        ),
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stapp_id', models.CharField(blank=True, default='', max_length=256)),
                ('access_token', models.CharField(blank=True, default='', max_length=256)),
                ('access_token_expired_at', models.DateTimeField(default=None, null=True)),
                ('refresh_token', models.TextField(default='', null=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Trigger',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pos', models.IntegerField(null=True)),
                ('text', models.TextField(max_length=128, null=True)),
                ('cap', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Capability')),
                ('chan', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='backend.Channel')),
                ('dev', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Device')),
            ],
        ),
        migrations.CreateModel(
            name='STCapability',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=30, unique=True)),
                ('command_type', models.TextField(null=True)),
                ('capabilities', models.ManyToManyField(to='backend.Capability')),
            ],
        ),
        migrations.CreateModel(
            name='StateLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('status', models.PositiveSmallIntegerField(choices=[(1, 'happend'), (2, 'current'), (3, 'to_occur')], default=1)),
                ('value', models.TextField()),
                ('value_type', models.CharField(choices=[('string', 'string'), ('number', 'number'), ('vector3', 'vector3'), ('enum', 'enum'), ('dynamic_enum', 'dynamic_enum'), ('color_map', 'color_map'), ('json_object', 'json_object'), ('date', 'date')], default='string', max_length=13)),
                ('is_superifttt', models.BooleanField(default=False)),
                ('cap', models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE, related_name='logcap', to='backend.Capability')),
                ('dev', models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE, related_name='logdev', to='backend.Device')),
                ('loc', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='logloc', to='backend.Location')),
                ('param', models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE, related_name='logparam', to='backend.Parameter')),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='State',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.BooleanField()),
                ('text', models.TextField(max_length=128, null=True)),
                ('cap', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Capability')),
                ('chan', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='backend.Channel')),
                ('dev', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Device')),
            ],
        ),
        migrations.CreateModel(
            name='Record',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('request', models.TextField(blank=True)),
                ('response', models.TextField(blank=True)),
                ('typ', models.TextField(choices=[('syn_first', 'First Time Synthesize'), ('syn_followup', 'Following-Up Synthesize'), ('debug_first', 'First Time Debug'), ('debug_followup', 'Following-Up Debug'), ('edit_rule', 'Edit Rule')])),
                ('location', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='backend.Location')),
            ],
        ),
        migrations.CreateModel(
            name='RangeSeparation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('min', models.FloatField(default=float("-inf"))),
                ('max', models.FloatField(default=float("inf"))),
                ('representative', models.FloatField()),
                ('count', models.IntegerField(default=0)),
                ('cap', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Capability')),
                ('dev', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Device')),
                ('param', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Parameter')),
            ],
        ),
        migrations.CreateModel(
            name='ParValMapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('st_val', models.TextField()),
                ('val', models.TextField()),
                ('param', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Parameter')),
            ],
        ),
        migrations.CreateModel(
            name='ParVal',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('val', models.TextField()),
                ('par', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Parameter')),
                ('state', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.State')),
            ],
        ),
        migrations.AddField(
            model_name='device',
            name='location',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='backend.Location'),
        ),
        migrations.AddField(
            model_name='device',
            name='users',
            field=models.ManyToManyField(to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='counter',
            name='dev',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Device'),
        ),
        migrations.AddField(
            model_name='counter',
            name='param',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Parameter'),
        ),
        migrations.CreateModel(
            name='Condition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('val', models.TextField()),
                ('comp', models.TextField(choices=[('=', 'is'), ('!=', 'is not'), ('<', 'is less than'), ('>', 'is greater than')])),
                ('par', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Parameter')),
                ('trigger', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Trigger')),
            ],
        ),
        migrations.CreateModel(
            name='ColorCount',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField(blank=True)),
                ('rgb', models.TextField(blank=True)),
                ('count', models.IntegerField(default=0)),
                ('cap', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Capability')),
                ('dev', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Device')),
                ('param', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Parameter')),
            ],
        ),
        migrations.AddField(
            model_name='capability',
            name='channels',
            field=models.ManyToManyField(to='backend.Channel'),
        ),
        migrations.CreateModel(
            name='ActionParVal',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('val', models.TextField()),
                ('par', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Parameter')),
                ('state', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.State')),
            ],
        ),
        migrations.CreateModel(
            name='ActionCondition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('val', models.TextField()),
                ('action', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Action')),
                ('par', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Parameter')),
            ],
        ),
        migrations.AddField(
            model_name='action',
            name='cap',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Capability'),
        ),
        migrations.AddField(
            model_name='action',
            name='chan',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='backend.Channel'),
        ),
        migrations.AddField(
            model_name='action',
            name='dev',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.Device'),
        ),
        migrations.CreateModel(
            name='SSRule',
            fields=[
                ('rule_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='backend.Rule')),
                ('priority', models.IntegerField()),
                ('action', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='SSactionstate', to='backend.Action')),
                ('triggers', models.ManyToManyField(to='backend.Trigger')),
            ],
            bases=('backend.rule',),
        ),
        migrations.CreateModel(
            name='SetParamOpt',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.TextField()),
                ('param', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.SetParam')),
            ],
        ),
        migrations.CreateModel(
            name='ESRule',
            fields=[
                ('rule_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='backend.Rule')),
                ('Etrigger', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='EStriggerE', to='backend.Trigger')),
                ('Striggers', models.ManyToManyField(to='backend.Trigger')),
                ('action', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ESactionstate', to='backend.Action')),
            ],
            bases=('backend.rule',),
        ),
    ]
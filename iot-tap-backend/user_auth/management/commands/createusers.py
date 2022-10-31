from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.cache import caches

from backend import models as m
import backend.util as util

import string
import random

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('token', type=str, help='the user token')
        parser.add_argument('-m', '--mode', type=str, help='The interface mode for the user (c, sn, nf, nn). ')
        parser.add_argument('--preload', help='Pre load example traces for this user', action='store_true')
    
    def handle(self, *args, **options):
        """
        This command is used to add new users
        """
        
        token = options['token']
        mode = options['mode']
        preload = options['preload']

        user_code_mode_list = [
            (token, mode),
        ]

        # this is for generating location tokens
        characters = string.ascii_letters + string.punctuation  + string.digits

        # create each user
        for code, mode in user_code_mode_list:
            # create the user itself
            init_scenario = m.Scenario.objects.get(stage=m.Scenario.INIT)
            user = m.User.objects.create(code=code, mode=mode, currentscenario=init_scenario)
            # create locations for the user
            for template_loc in m.Location.objects.filter(is_template=True):
                token = str(user.id) + str(template_loc.id) + "".join(random.choice(characters) for _ in range(16))
                location = m.Location.objects.create(user=user, is_template=False, scenario=template_loc.scenario, token=token)
                # copy rules
                for esrule in m.ESRule.objects.filter(location=template_loc):
                    util.deep_copy_esrule(esrule, location)

                # copy device monitors
                for dev_monitor in m.DeviceMonitor.objects.filter(loc=template_loc):
                    m.DeviceMonitor.objects.create(
                        cap=dev_monitor.cap,
                        dev=dev_monitor.dev,
                        param=dev_monitor.param,
                        loc=location,
                        value_type=dev_monitor.value_type,
                        target=dev_monitor.target
                    )

                # copy traces if mode preload is set
                if preload:
                    for state_log in m.StateLog.objects.filter(loc=template_loc).order_by('timestamp', 'id'):
                        m.StateLog.objects.create(
                            timestamp = state_log.timestamp,
                            status=state_log.status,
                            cap=state_log.cap,
                            dev=state_log.dev,
                            param=state_log.param,
                            loc=location,
                            value=state_log.value,
                            value_type=state_log.value_type,
                            is_superifttt=state_log.is_superifttt
                        )


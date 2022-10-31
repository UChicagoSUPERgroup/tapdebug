from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.cache import caches

from backend import models as m
import backend.util as util

import string
import random

class Command(BaseCommand):
    def handle(self, *args, **options):
        """
        This command is used to replate a template location with a user's location
        """
        
        usercode = input('Please input usercode: ')
        stage = input('Please input stage - t(utorial)/s(urvey): ')
        task = input('Please input task id: ')
        task = int(task)
        mode = input('(A)ppend or (R)place: ')

        scenario = m.Scenario.objects.get(stage=stage, task=task)
        # find the location related to usercode
        location_orig = m.Location.objects.get(scenario=scenario, user__code=usercode)
        # find the target location
        location_targ = m.Location.objects.get(scenario=scenario, is_template=True)

        # copy rules
        # for esrule in m.ESRule.objects.filter(location=location_orig):
        #     util.deep_copy_esrule(esrule, location_targ)

        # remove existing traces if aimming to replace traces
        if mode == 'R':
            for state_log in m.StateLog.objects.filter(loc=location_targ):
                state_log.delete()

        # copy traces
        for state_log in m.StateLog.objects.filter(loc=location_orig).order_by('timestamp', 'id'):
            m.StateLog.objects.create(
                timestamp = state_log.timestamp,
                status=state_log.status,
                cap=state_log.cap,
                dev=state_log.dev,
                param=state_log.param,
                loc=location_targ,
                value=state_log.value,
                value_type=state_log.value_type,
                is_superifttt=state_log.is_superifttt
            )


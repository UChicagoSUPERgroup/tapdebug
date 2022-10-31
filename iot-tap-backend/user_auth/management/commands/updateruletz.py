from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.cache import caches

from autotapta.input.IoTCore import inputTraceFromList, updateTraceFromList
from backend import models as m
from autotap.util import generate_dict_from_state_log, initialize_trace_for_location
from autotap.translator import generate_all_device_templates, generate_boolean_map
from backend.util import check_regular_s_trig

import datetime
from pytz import timezone, utc
from timezonefinder import TimezoneFinder


class Command(BaseCommand):
    def handle(self, *args, **options):
        """
        This is used to add the location field in all existing state logs
        """
        for rule in m.Rule.objects.all():
            esrule = rule.esrule
            location = m.Location.objects.get(st_installed_app_id=rule.st_installed_app_id)
            tf = TimezoneFinder()
            location_tz = tf.timezone_at(lng=location.lon, lat=location.lat)
            e_trigger = esrule.Etrigger
            if e_trigger.cap.id == 25:
                for pv in m.Condition.objects.filter(trigger=e_trigger):
                    utc_time = datetime.time(hour=int(pv.val.split(':')[0]), 
                                             minute=int(pv.val.split(':')[1]))
                    utc_time = utc_time.replace(tzinfo=utc)
                    local_time = datetime.datetime.combine(datetime.datetime.today(), utc_time).astimezone(
                        timezone(location_tz)).timetz()
                    print(pv.val, end='')
                    print(' ====> ', end='')
                    pv.val = '%02d:%02d' % (local_time.hour, local_time.minute)
                    print(pv.val)
                    pv.save()
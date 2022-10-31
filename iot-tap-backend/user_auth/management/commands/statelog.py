from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.cache import caches

from autotapta.input.IoTCore import inputTraceFromList, updateTraceFromList
from autotapta.analyze.Analyze import filterFlipping
from autotapta.model.Trace import enhanceTraceWithTiming
from autotapta.analyze.Rank import calcScoreEnhanced, analyzeTimeOrder
from backend import models as m
from autotap.util import generate_dict_from_state_log, initialize_trace_for_location, get_trace_for_location, generate_clip
from autotap.translator import generate_all_device_templates, generate_boolean_map, translate_clause_into_autotap_tap, \
    generate_cap_time_list_from_tap

import json
import math
from datetime import datetime
import pytz


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('command', type=str, help='list: list all location; show: show the state logs')
        parser.add_argument('-i', '--index', type=int, help='The index of the location to be shown')
    
    def list_locations(self):
        locations = list(m.Location.objects.all().order_by('id'))
        for index in range(len(locations)):
            location = locations[index]
            print('%d (%s):\t' % (index, str(location)))

    def show_statelogs(self, entry):
        locations = list(m.Location.objects.all().order_by('id'))
        location = locations[entry]

        state_logs = list(m.StateLog.objects.filter(loc=location).order_by('timestamp', 'id'))

        for state_log in state_logs:
            print(state_log.id, state_log.timestamp, state_log.dev.name,
                  state_log.cap.name, state_log.param.name, state_log.value, 
                  '@' if state_log.is_superifttt else '')

    def init_trace(self, entry):
        locations = list(m.Location.objects.all().order_by('id'))
        location = locations[entry]

        initialize_trace_for_location(location, True)

    def show_trace(self, entry):
        locations = list(m.Location.objects.all().order_by('id'))
        location = locations[entry]

        trace = get_trace_for_location(location)
        for time, action in trace.actions:
            print(time, action)

    def clear_trace(self, entry):
        locations = list(m.Location.objects.all().order_by('id'))
        location = locations[entry]

        state_logs = list(m.StateLog.objects.filter(loc=location).order_by('timestamp', 'id'))

        for state_log in state_logs:
            state_log.delete()
    
    def handle(self, *args, **options):
        """
        This is used to add the location field in all existing state logs
        """
        command = options['command']

        if command == 'list':
            self.list_locations()
        elif command == 'show':
            try:
                entry = options['index']
                self.show_statelogs(entry)
            except IndexError:
                raise Exception('Need to have index for the show command')
        elif command == 'showtrace':
            try:
                entry = options['index']
                self.show_trace(entry)
            except IndexError:
                raise Exception('Need to have index for the show command')
        elif command == 'inittrace':
            try:
                entry = options['index']
                self.init_trace(entry)
            except IndexError:
                raise Exception('Need to have index for the show command')
        elif command == 'clear':
            try:
                entry = options['index']
                self.clear_trace(entry)
                self.init_trace(entry)
            except IndexError:
                raise Exception('Need to have index for the show command')
        else:
            raise Exception('unknown command %s' % command)

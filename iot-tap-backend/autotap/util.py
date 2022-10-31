from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.core.cache import cache, caches
from django.utils.crypto import get_random_string
import backend.models as m
import os, sys
from autotapta.input.IoTCore import inputTraceFromList, updateTraceFromList
from autotapta.model.Trace import Trace
from autotapmc.model.Tap import Tap

from django.conf import settings
from django.utils.timezone import make_aware
from django.views.decorators.csrf import csrf_exempt
from autotap.variable import find_closest_color
from autotap.variable import generate_all_device_templates, generate_boolean_map
from autotap.translator import split_autotap_formula, generate_cap_time_list_from_tap

import itertools
import json
import datetime
import copy
from numpy import array
from pytz import timezone, utc
from timezonefinder import TimezoneFinder


def generate_dict_from_state_log(state_log, cluster=False):
    if not cluster:
        value = state_log.value
    else:
        param = state_log.param
        cap = state_log.cap
        dev = state_log.dev
        
        if param.type == 'range':
            range_seps = m.RangeCounter.objects.filter(param=param, cap=cap, dev=dev, 
                                                       min__lte=float(state_log.value), 
                                                       max__gt=float(state_log.value))
            if range_seps:
                # should be only one
                range_sep = list(range_seps)[0]
                value = range_sep.representative
            else:
                value = state_log.value
        elif param.type == 'color':
            color_name = find_closest_color(state_log.value)
            value = color_name
        else:
            value = state_log.value

    result = {
        'time': state_log.timestamp.strftime('%4Y-%m-%d %H:%M:%S'),
        'device_id': str(state_log.dev.id),
        'device_name': state_log.dev.name,
        'capability': state_log.cap.name,
        'attribute': state_log.param.name,
        'current_value': str(value),
        'external': not state_log.is_superifttt, 
        'is_changed': "true"
    }
    return result


def update_trace_in_cache(state_log):
    location = state_log.loc
    trace_cache = caches['trace']
    cached_trace = trace_cache.get(str(location.id))

    if cached_trace is None:
        initialize_trace_for_location(state_log.loc, rewrite=False)
    else:
        # Get old logs
        template_dict = cached_trace['template_dict']
        boolean_map = cached_trace['boolean_map']
        trace = cached_trace['trace']

        # Timezone of the current location
        tf = TimezoneFinder()
        location_tz = tf.timezone_at(lng=location.lon, lat=location.lat)

        # Get new logs
        log_list = [generate_dict_from_state_log(state_log, cluster=True)]

        # Insert new logs into old ones
        trace = updateTraceFromList(trace, log_list, template_dict=template_dict, 
                                    boolean_map=boolean_map, if_disting_ext=True)
        # Store new trace into cache
        cached_trace['trace'] = trace
        cached_trace['timestamp'] = state_log.timestamp

        trace_cache.set(str(location.id), cached_trace)
        
        return trace


def initialize_trace_for_location(loc, rewrite=True):
    trace_cache = caches['trace']
    if not rewrite and trace_cache.get(str(loc.id)) is not None:
        return None
    # Fetch logs from the database
    state_logs = m.StateLog.objects.filter(loc=loc).order_by('timestamp', 'id')
    log_list = [generate_dict_from_state_log(state_log, cluster=True) for state_log in state_logs.iterator()]
    # Translate trace, gather important information
    template_dict = generate_all_device_templates()
    boolean_map = generate_boolean_map()
    trace = inputTraceFromList(log_list, trunc_none=True, 
                            template_dict=template_dict, boolean_map=boolean_map, if_disting_ext=True)
    # Store information in cache
    cached_trace = {
        'template_dict': template_dict, 
        'boolean_map': boolean_map, 
        'timestamp': datetime.datetime.now(), 
        'trace': trace
    }
    trace_cache.set(str(loc.id), cached_trace)
    return trace


# Initialize trace from the log list
# This function bypass statelog queries
def initialize_trace_from_log_list(loc, log_list):
    trace_cache = caches['trace']
    template_dict = generate_all_device_templates()
    boolean_map = generate_boolean_map()
    trace = inputTraceFromList(log_list, trunc_none=True, 
                            template_dict=template_dict, boolean_map=boolean_map, if_disting_ext=True)
    # Store information in cache
    cached_trace = {
        'template_dict': template_dict, 
        'boolean_map': boolean_map, 
        'timestamp': datetime.datetime.now(), 
        'trace': trace
    }
    trace_cache.set(str(loc.id), cached_trace)
    return trace


def get_trace_for_location(location):
    trace_cache = caches['trace']
    cached_trace = trace_cache.get(str(location.id))
    if cached_trace is None:
        trace = initialize_trace_for_location(location)
    else:
        trace = cached_trace['trace']
    return trace


def get_sensor_dev_cap(rule_clause):
    result = []
    for if_clause in rule_clause['ifClause']:
        dev_clause = if_clause['device']
        cap_clause = if_clause['capability']
        dev_name = dev_clause['name']

        if dev_clause['name'] != 'Clock':
            result.append((dev_name, cap_clause['name']))
        else:
            for par, par_val in zip(if_clause['parameters'], if_clause['parameterVals']):
                if par['type'] == 'meta':
                    d_c = par_val['value']['device']
                    c_c = par_val['value']['capability']
                    d_name = d_c['name']
                    result.append((d_name, c_c['name']))
    
    return result


def get_action_dev_cap(rule_clause):
    then_clause = rule_clause['thenClause'][0]
    dev_clause = then_clause['device']
    cap_clause = then_clause['capability']
    dev_name = dev_clause['name'] if not dev_clause['label'] else dev_clause['label']
    return dev_name, cap_clause['name']


def get_sensor_dev_cap_django(rule):
    result = []
    esrule = rule.esrule

    for trigger in [esrule.Etrigger] + list(esrule.Striggers.all()):
        dev = trigger.dev
        cap = trigger.cap
        dev_name = dev.name if not dev.label else dev.label

        if dev.name != 'Clock':
            result.append((dev_name, cap.name))
        else:
            conditions = m.Condition.objects.filter(trigger=trigger)
            for condition in conditions:
                par = condition.par
                val = condition.val
                if par.type == 'meta':
                    val_clause = json.loads(val.replace('\'', '\"'))
                    d_c = val_clause['device']
                    c_c = val_clause['capability']
                    d_name = d_c['name'] if not d_c['label'] else d_c['label']
                    result.append((d_name, c_c['name']))
    
    return result


def get_action_dev_cap_django(rule):
    esrule = rule.esrule
    action = esrule.action
    dev = action.dev
    cap = action.cap
    dev_name = dev.name if not dev.label else dev.label
    return dev_name, cap.name


def merge_times(primary_list, secondary_list, diff):
    """
    merge two time lists
    for each time in the secondary list, 
    if exist a time in the primary list that is really close, don't put into final list
    """
    if not primary_list:
        return secondary_list
    if not secondary_list:
        return primary_list
    
    index_p = 0
    index_s = 0

    n_p = len(primary_list)
    n_s = len(secondary_list)

    final_list = []

    while index_p != n_p - 1 or index_s != n_s - 1:
        if index_p != n_p - 1 and index_s != n_s - 1:
            if primary_list[index_p] < secondary_list[index_s]:
                final_list.append(primary_list[index_p])
                index_p += 1
            else:
                if secondary_list[index_s] - primary_list[index_p] < diff and \
                    -diff < secondary_list[index_s] - primary_list[index_p+1] < diff:
                    index_s += 1
                else:
                    final_list.append(secondary_list[index_s])
                    index_s += 1
        elif index_p != n_p - 1:
            final_list.append(primary_list[index_p])
            index_p += 1
        elif index_s != n_s - 1:
            if secondary_list[index_s] - primary_list[n_p-1] < diff:
                index_s += 1
            else:
                final_list.append(secondary_list[index_s])
                index_s += 1
        else:
            break
    
    return final_list


def find_time_clips(time_list, span):
    """
    given a time_list, find time clips that cover all of them
    """
    holding_starting_time = None
    current_time = None
    time_clips = []

    for time in time_list:
        if holding_starting_time is None:
            holding_starting_time = time - span
            current_time = time
        else:
            if time > current_time + span:
                time_clips.append((holding_starting_time, current_time + span))
                holding_starting_time = time - span
                current_time = time
            else:
                current_time = time
    
    if holding_starting_time is not None:
        time_clips.append((holding_starting_time, current_time + span))
    
    return time_clips


def generate_clip(trace, start_time, end_time):
    # extract all actions that is within time range
    actions_index = [(index, action_tup)
                        for action_tup, index in zip(trace.actions, range(len(trace.actions)))
                        if action_tup[0] >= start_time and action_tup[0] < end_time]
    if not actions_index:
        post_index = [(index, action_tup)
                      for action_tup, index in zip(trace.actions, range(len(trace.actions)))
                      if action_tup[0] >= start_time]
        if not post_index:
            # should be using the final state
            if trace.actions:
                trace.system.restoreFromStateVector(trace.pre_condition[-1])
                if '*' not in trace.actions[-1][1] and '#' not in trace.actions[-1][1]:
                    trace.system.applyAction(trace.actions[-1][1])
                initial_state = trace.system.saveToStateVector()
            else:
                initial_state = trace.initial_state
            initial_actions = []
        else:
            # should be using the pre_cond
            initial_state = trace.pre_condition[post_index[0][0]]
            initial_actions = []
    else:
        # extract informations of those actions
        indexs = [index for index, _ in actions_index]
        actions = [action_tup for _, action_tup in actions_index]
        is_ext_list = [trace.is_ext_list[index] for index in indexs]
        initial_actions = [(*action_tup, is_ext) for action_tup, is_ext in zip(actions, is_ext_list)]
        initial_state = trace.pre_condition[indexs[0]]

    # generate trace
    episode_trace = Trace(initial_state, trace.system, initial_actions, start_time=start_time, end_time=end_time)
    
    return episode_trace


def translate_value(cap, val, rev_map):
    _, _, parameter, p_map = rev_map[cap]
    if parameter.type not in {'bin'}:
        return val
    else:
        val = str(val).lower()
        return p_map[val]
        

def push_entry(time_dict, target_action, time, index, cap_dict, shown_new_tap, rev_map):
    cap, val = target_action.split('=')
    val = translate_value(cap, val, rev_map)
    date_str = time.strftime('%Y-%m-%d %H:%M')
    if index == -1:  # orig rule
        val = 'orig_triggered[%s]' % val
    else:  # new rule
        shown_new_tap.add(index)
        val = '%d_triggered[%s]' % (index, val)
    time_dict[date_str][cap_dict[cap]].append(val)

    
def translate_time_clip(clip, target_action, time_list_t, n_new_tap, rev_map):
    field_name_list = clip.system.getFieldNameList()
    cap_dict = {cap: index for cap, index in zip(field_name_list, range(len(field_name_list)))}
    # initialize dictionary time_dict[(date, hour, minute)][cap_id]
    time_dict = dict()
    shown_new_tap = set()
    start_time_i = datetime.datetime(year=clip.start_time.year, 
                                     month=clip.start_time.month, 
                                     day=clip.start_time.day, 
                                     hour=clip.start_time.hour, 
                                     minute=clip.start_time.minute)
    end_time_i = datetime.datetime(year=clip.end_time.year, 
                                   month=clip.end_time.month, 
                                   day=clip.end_time.day, 
                                   hour=clip.end_time.hour, 
                                   minute=clip.end_time.minute)
    time = start_time_i
    while time <= end_time_i:
        date_str = time.strftime('%Y-%m-%d %H:%M')
        time_dict[date_str] = [[] for _ in range(len(clip.system.getFieldNameList()))]
        time += datetime.timedelta(minutes=1)
    time_dict[''] = [[] for _ in range(len(clip.system.getFieldNameList()))]

    index_time_list = 0
    current_time = clip.start_time

    # Should push the initial status into the dictionary
    for cap in cap_dict:
        cap_index = cap_dict[cap]
        val = clip.initial_state[cap_index]
        val = translate_value(cap, val, rev_map)
        time_dict[''][cap_index].append(val)
    
    for ta, is_ext in zip(clip.actions, clip.is_ext_list):
        time, action = ta
        while index_time_list <= len(time_list_t)-1 and time_list_t[index_time_list][0] < time:
            if time_list_t[index_time_list][0] >= current_time:
                push_entry(time_dict, target_action, time_list_t[index_time_list][0], 
                           time_list_t[index_time_list][1], cap_dict, 
                           shown_new_tap=shown_new_tap, rev_map=rev_map)
                
            index_time_list += 1
        # Now push the action into the dictionary
        if '*' not in action and 'clock.clock_time' not in action:
            cap, val = action.split('=')
            val = translate_value(cap, val, rev_map)
            date_str = time.strftime('%Y-%m-%d %H:%M')

            val = val if is_ext or not action == target_action else 'orig_triggered[%s]' % val
            time_dict[date_str][cap_dict[cap]].append(val)
        
        current_time = time
    
    while index_time_list <= len(time_list_t)-1 and time_list_t[index_time_list][0] < clip.end_time:
        if time_list_t[index_time_list][0] >= current_time:
            push_entry(time_dict, target_action, time_list_t[index_time_list][0], 
                       time_list_t[index_time_list][1], cap_dict, 
                       shown_new_tap=shown_new_tap, rev_map=rev_map)
        index_time_list += 1
    
    date_str_list = sorted(list(time_dict.keys()))
    for date_str in date_str_list:
        if all([not lst for lst in time_dict[date_str]]):
            del time_dict[date_str]
        else:
            break
    date_str_list.reverse()
    for date_str in date_str_list:
        if all([not lst for lst in time_dict[date_str]]):
            del time_dict[date_str]
        else:
            break

    return time_dict, shown_new_tap


# helper for translating time clips for debug and feedback views
# for debug: just generate time clips. it should put "orig" labels
# for feedback: same as debug, but also need to get a references for all automated actions
# if there are unactuated actions, send them in through unactuated_list (time, event, pre_cond)
# when it is called by debug, if the target action that has been fixed was initially unactuated
# put it in as (time, event, pre_cond) in debug_unactuated_tup
# the event should be the target action instead of the triggering action
# the returned ref_dict has (date_str, cap_id, entry_id) as key and the index of action as value
def translate_time_clip_helper(clip, target_action_id, rev_map, unactuated_list=None, debug_unactuated_tup=None):
    field_name_list = clip.system.getFieldNameList()
    cap_dict = {cap: index for cap, index in zip(field_name_list, range(len(field_name_list)))}

    time_dict = dict()
    start_time_i = datetime.datetime(year=clip.start_time.year, 
                                     month=clip.start_time.month, 
                                     day=clip.start_time.day, 
                                     hour=clip.start_time.hour, 
                                     minute=clip.start_time.minute)
    end_time_i = datetime.datetime(year=clip.end_time.year, 
                                   month=clip.end_time.month, 
                                   day=clip.end_time.day, 
                                   hour=clip.end_time.hour, 
                                   minute=clip.end_time.minute)
    time = start_time_i
    while time <= end_time_i:
        date_str = time.strftime('%Y-%m-%d %H:%M')
        time_dict[date_str] = [[] for _ in range(len(clip.system.getFieldNameList()))]
        time += datetime.timedelta(minutes=1)
    time_dict[''] = [[] for _ in range(len(clip.system.getFieldNameList()))]

    # Should push the initial status into the dictionary
    for cap in cap_dict:
        cap_index = cap_dict[cap]
        val = clip.initial_state[cap_index]
        val = translate_value(cap, val, rev_map)
        time_dict[''][cap_index].append(val)
    unactuated_index = 0
    debug_unactuated_pushed = False
    reference_dict = {}
    for index in range(len(clip.actions)):
        time, action = clip.actions[index]
        is_ext = clip.is_ext_list[index]
        # Push unactuated actions into the dictionary first
        if unactuated_list is not None:
            while unactuated_index < len(unactuated_list) and unactuated_list[unactuated_index][0] <= time:
                cap, val = unactuated_list[unactuated_index][1].split('=')
                val = translate_value(cap, val, rev_map)
                val = 'orign_triggered[%s]' % val
                entry_id = len(time_dict[date_str][cap_dict[cap]])
                reference_dict[(date_str, cap_dict[cap], entry_id)] = -unactuated_index-1  # TODO: this is temp
                time_dict[date_str][cap_dict[cap]].append(val)
                unactuated_index += 1

        # Push unactuated fixed actions into the dictionary
        if debug_unactuated_tup is not None and not debug_unactuated_pushed:
            unactuated_time, unactuated_action, _ = debug_unactuated_tup
            if unactuated_time <= time:
                cap, val = unactuated_action.split('=')
                val = translate_value(cap, val, rev_map)
                val = 'deln_triggered[%s]' % val
                entry_id = len(time_dict[date_str][cap_dict[cap]])
                reference_dict[(date_str, cap_dict[cap], entry_id)] = -1  # TODO: this is temp
                time_dict[date_str][cap_dict[cap]].append(val)
                debug_unactuated_pushed = True

        # Now push the action into the dictionary
        if '*' not in action and not action.startswith('clock.clock_time'):
            cap, val = action.split('=')
            val = translate_value(cap, val, rev_map)
            date_str = time.strftime('%Y-%m-%d %H:%M')
            
            if target_action_id == index:
                val = 'del_triggered[%s]' % val
            else:
                if not is_ext:
                    # if this is a triggered action, we should put orig_triggered label
                    # we should also store the ref so that we can refer to the event in a trace
                    # when we get feedback from frontend
                    val = 'orig_triggered[%s]' % val
                    entry_id = len(time_dict[date_str][cap_dict[cap]])
                    reference_dict[(date_str, cap_dict[cap], entry_id)] = index
            
            time_dict[date_str][cap_dict[cap]].append(val)
    
    return time_dict, reference_dict


def translate_time_clip_debug(clip, target_action_id, rev_map, debug_unactuated_tup=None):
    time_dict, _ =  translate_time_clip_helper(clip, target_action_id, rev_map, debug_unactuated_tup=debug_unactuated_tup)
    return time_dict


def translate_time_clip_feedback(clip, rev_map, unactuated_list=None):
    time_dict, reference_dict =  translate_time_clip_helper(clip, -1, rev_map, unactuated_list=unactuated_list)
    return time_dict, reference_dict


def modify_patch_to_taps(orig_taps, modify_patch):
    index = modify_patch['index']
    new_cond = modify_patch['new_condition']
    new_taps = []
    for ii in range(len(orig_taps)):
        orig_tap = orig_taps[ii]
        if ii == index:
            new_conditions = orig_tap.condition + [new_cond]
            tap = Tap(action=orig_tap.action, trigger=orig_tap.trigger, condition=new_conditions)
        else:
            tap = orig_tap
        new_taps.append(tap)
    return new_taps


def delete_patch_to_taps(orig_taps, delete_patch):
    index = delete_patch['index']
    new_taps = [orig_taps[ii] for ii in range(len(orig_taps)) if ii != index]
    return new_taps


# get all caps shown up in a list of trigger action rules (in autotap format)
def get_all_caps_in_taps(tap_list, only_cond=False):
    cap_set = set()
    for tap in tap_list:
        if not only_cond:
            dev, cap, par, _, _ = split_autotap_formula(tap.trigger)
            cap = dev + '.' + cap + '_' + par
            if cap != 'clock.clock_time':
                cap_set.add(cap)
            dev, cap, par, _, _ = split_autotap_formula(tap.action)
            cap = dev + '.' + cap + '_' + par
            cap_set.add(cap)
            # if cap not in cap_trigger_list:
            #     cap_trigger_list.append(cap)
        for cond in tap.condition:
            dev, cap, par, _, _ = split_autotap_formula(cond)
            cap = dev + '.' + cap + '_' + par
            cap_set.add(cap)
    return list(cap_set)


# get all time related information from list of tap
# cap time information, for what cap we have: (xxx has been xxx for exactly x time)?
#                       arrange in list of tuples (capname, time_in_second)
# clock information, for what time we have a clock trigger (it becomes xx:xx)
#                       arrange in list of ints (translate 24h time format to second)
def get_time_information_from_taps(tap_list):
    cap_time_set = set()
    for tap in tap_list:
        for cap_time in generate_cap_time_list_from_tap(tap):
            if cap_time not in cap_time_set:
                cap_time_set.add(cap_time)
    cap_time_list = list(cap_time_set)

    clock_set = set()
    for tap in tap_list:
        dev, cap, par, _, val = split_autotap_formula(tap.trigger)
        if dev == 'clock' and cap == 'clock' and par == 'time':
            clock_set.add(int(val))
    clock_list = list(clock_set)

    return cap_time_list, clock_list


# apply a patch and return the new tap_list
def apply_tap_patch(orig_tap_list, patch):
    new_tap_list = copy.deepcopy(orig_tap_list)
    if patch['mode'] == 'add-rule':
        new_tap = patch['new_rule']
        new_tap_list.append(new_tap)
    elif patch['mode'] == 'delete-rule':
        rule_id = patch['rule_id']
        del new_tap_list[rule_id]
    elif patch['mode'] == 'add-condition':
        rule_id = patch['rule_id']
        new_tap_list[rule_id].condition.append(patch['new_condition'])
    elif patch['mode'] == 'delete-condition':
        rule_id = patch['rule_id']
        cond_id = patch['condition_id']
        del new_tap_list[rule_id].condition[cond_id]
    elif patch['mode'] == 'modify-condition':
        rule_id = patch['rule_id']
        cond_id = patch['condition_id']
        new_tap_list[rule_id].condition[cond_id] = patch['new_condition']
    else:
        raise Exception('Unknown patch type: ' + patch['mode'])
    return new_tap_list


# get complexity for patch
# this determines the order in which patches are displayed
def tap_patch_complexity(patch):
    if patch['mode'] == 'add-rule':
        return 1 + len(patch['new_rule'].condition)
    else:
        return 0




# get meta information about trace
# e.g. for each (dev, cap) maximum value, minimum value
def getTraceMeta(trace):

    # util functions
    def _dev_name_to_autotap(name):
        name = name.replace(' ', '_').lower()
        name = ''.join([ch for ch in name if ch.isalnum() or ch == '_'])
        return name

    def _cap_name_to_autotap(name):
        name = name.replace(' ', '_')
        name = ''.join([ch for ch in name if ch.isalnum() or ch == '_'])
        name = name.lower()
        return name

    # get maximum value and minimum value
    max_cap_dict = {}
    max_time_dict = {}
    min_cap_dict = {}
    min_time_dict = {}
    for t, a in trace.actions:
        if '*' not in a and 'clock' not in a :
            dev, val = a.split('=')
            if val.isdigit():
                # we only track min max values for range caps
                val = float(val)
                if dev not in max_cap_dict:
                    max_cap_dict[dev] = val
                    max_time_dict[dev] = str(t)
                else:
                    if val > max_cap_dict[dev]:
                        max_cap_dict[dev] = val
                        max_time_dict[dev] = str(t)
                if dev not in min_cap_dict:
                    min_cap_dict[dev] = val
                    min_time_dict[dev] = str(t)
                else:
                    if val < min_cap_dict[dev]:
                        min_cap_dict[dev] = val
                        min_time_dict[dev] = str(t)
    
    min_max_dict = {}

    dev_list_backend = list(m.Device.objects.all().order_by('id'))
    dev_name_list = [_dev_name_to_autotap(dev.name) for dev in dev_list_backend]
    cap_list_backend = list(m.Capability.objects.all().order_by('id'))
    cap_name_list = [_cap_name_to_autotap(cap.name) for cap in cap_list_backend]
    for dev_cap in max_cap_dict:
        # for each dev_cap, i.e. "xxx.yyy" in xxx.yyy=zzz
        # find the (dev.id, cap.id) and map it to the min value and max value
        dev_autotap, cap_autotap, _, _, _ = split_autotap_formula(dev_cap+'=0')
        try:
            device = dev_list_backend[dev_name_list.index(dev_autotap)]
            capability = cap_list_backend[cap_name_list.index(cap_autotap)]
        except ValueError:
            pass
        min_max_dict['%d,%d' % (device.id, capability.id)] = {
            'max': max_cap_dict[dev_cap], 'min': min_cap_dict[dev_cap], 'max_time': max_time_dict[dev_cap], 'min_time': min_time_dict[dev_cap]}

    return {'min_max': min_max_dict}

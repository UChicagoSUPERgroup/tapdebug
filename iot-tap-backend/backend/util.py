# model-related
from django.db.models import Q
from django.utils import timezone
from django.conf import settings
from . import models as m

# functionality
import operator as op
import datetime, random, re, traceback
from autotapta.analyze.Cluster import clusterRangeVars
from autotapta.input.Template import translateCapability
from autotapta.analyze.Analyze import extractEpisodes, extractTriggerCases, extractRevertCases
from autotapta.analyze.Rank import checkIfEpisodeCovered
from autotap.util import update_trace_in_cache
from autotap.variable import update_separation_count
from backend.translator import time_to_int

import json
import webcolors
from timezonefinder import TimezoneFinder
from pytz import utc
from pytz import timezone as pytz_timezone

######################################
######################################
## INDEX                            ##
## FES :: FRONTEND / SELECTORS      ##
## STV :: ST-END VIEWS              ##
## RC  :: RULE CREATION             ##
## SPC :: SAFETY PROPERTY CREATION  ##
## SLM :: STATELOG MANAGEMENT       ##
## DM  :: DEVICE MANAGEMENT         ##
######################################
######################################

################################################################################
## [FES] FRONTEND / SELECTORS
################################################################################

def get_or_make_user(code,mode):
    try:
        user = m.User_ICSE19.objects.get(code=code)
    except m.User_ICSE19.DoesNotExist:
        user = m.User_ICSE19(code=code,mode=mode)
        user.save()
    return user

### @TO_DELETE: Potentially dead code
# return id:name dict of all devices
# def all_devs(user):
#     json_resp = {}
#     for dev in m.Device.objects.filter(users__contains=user):
#         json_resp[dev.id] = dev.name
#     return json_resp

### @TO_DELETE: Potentially dead code
# def user_devs(user):
#     if isinstance(user, m.User):
#         mydevs = m.Device.objects.filter(users__contains=user)
#     else:
#         mydevs = m.Device.objects.filter(owner=user)
#     pubdevs = m.Device.objects.filter(public=True)
#     return mydevs.union(pubdevs)

# return id:name dict of all channels
def valid_chans(user,is_trigger):
    json_resp = {'chans' : []}
    # for integration of user and user_icse19
    if isinstance(user, m.User):
        chans = m.Channel.objects.filter(Q(device__users__in=[user])).distinct().order_by('name')
        devs = m.Device.objects.filter(Q(users__in=[user]))
    else:
        chans = m.Channel.objects.filter(Q(capability__device__public=True)).distinct().order_by('name')
        devs = m.Device.objects.filter(Q(public=True))
    chans = filter(lambda x : chan_has_valid_cap(x,devs,is_trigger),chans)
    for chan in chans:
        json_resp['chans'].append({'id' : chan.id, 'name' : chan.name, 'icon' : chan.icon})
    return json_resp

def dev_has_valid_cap(dev,channel,is_trigger):
    poss_caps = dev.caps.all().intersection(m.Capability.objects.filter(channels=channel))
    if is_trigger:
        return any(map(lambda x : x.readable,poss_caps))
    else:
        return any(map(lambda x : x.writeable,poss_caps))

def dev_has_valid_cap_no_channel(dev, is_trigger):
    poss_caps = dev.caps.all()
    if is_trigger:
        return any(map(lambda x : x.readable,poss_caps))
    else:
        return any(map(lambda x : x.writeable,poss_caps))

def chan_has_valid_cap(chan,devs,is_trigger):
    dev_caps = m.Capability.objects.none()
    for dev in devs:
        dev_caps = dev_caps.union(dev.caps.all())
    poss_caps = m.Capability.objects.filter(channels=chan).intersection(dev_caps)
    if is_trigger:
        return any(map(lambda x : x.readable,poss_caps))
    else:
        return any(map(lambda x : x.writeable,poss_caps))

def rwfilter_caps(caps,is_trigger):
    if is_trigger:
        return filter((lambda x : x.readable),caps)
    else:
        return filter((lambda x : x.writeable),caps)

def map_labels(caps,is_trigger,is_event):
    if is_trigger:
        if is_event:
            return list(map((lambda x : (x.id,x.name,x.eventlabel, x.timeeventlabel)),caps))
        else:
            return list(map((lambda x : (x.id,x.name,x.statelabel, "")),caps))
    else:
        return list(map((lambda x : (x.id,x.name,x.commandlabel, "")),caps))

def filtermap_caps(caps,is_trigger,is_event):
    return map_labels(rwfilter_caps(caps,is_trigger),is_trigger,is_event)


###############################################################################
## [RC] RULE CREATION
###############################################################################

def get_or_make_state(cap, dev, value, is_action=False):
    '''
    Get the state of a cap/dev pair, or create one if none exists
    '''
    state, created = m.State.objects.get_or_create(cap=cap,dev=dev,action=is_action)
    state.text = "{}".format(value)
    state.save()
    return state


def deep_copy_trigger(trigger):
    '''
    deep copy a trigger
    '''
    new_trigger = m.Trigger(
        chan=trigger.chan,
        dev=trigger.dev,
        cap=trigger.cap,
        pos=trigger.pos,
        text=trigger.text,
        time_val=trigger.time_val
    )
    new_trigger.save()

    for cond in m.Condition.objects.filter(trigger=trigger):
        new_cond = m.Condition(
            par=cond.par,
            val=cond.val,
            comp=cond.comp,
            trigger=new_trigger
        )
        new_cond.save()
    
    return new_trigger


def deep_copy_action(action):
    '''
    deep copy an action
    '''
    new_action = m.Action(
        chan=action.chan,
        dev=action.dev,
        cap=action.cap,
        text=action.text
    )
    new_action.save()

    for cond in m.ActionCondition.objects.filter(action=action):
        new_cond = m.ActionCondition(
            par=cond.par,
            val=cond.val,
            action=new_action
        )
        new_cond.save()
    
    return new_action


def deep_copy_esrule(esrule, new_loc):
    '''
    deep copy an esrule into a new location new_loe
    '''
    new_etrigger = deep_copy_trigger(esrule.Etrigger)
    new_action = deep_copy_action(esrule.action)

    new_esrule = m.ESRule(
        location=new_loc,
        type='es',
        Etrigger=new_etrigger,
        action=new_action
    )

    new_esrule.save()
    new_esrule.Etrigger.rule = new_esrule
    new_esrule.Etrigger.save()
    new_esrule.action.rule = new_esrule
    new_esrule.action.save()
    new_esrule.save()

    for s_trig in esrule.Striggers.all():
        new_s_trig = deep_copy_trigger(s_trig)
        new_s_trig.rule = new_esrule
        new_s_trig.save()
        new_esrule.Striggers.add(new_s_trig)
    
    return new_esrule


###############################################################################
## [SPC] SAFETY PROPERTY CREATION
###############################################################################

def display_trigger(trigger):
    return {'channel' : {'icon' : trigger.chan.icon}, 'text' : trigger.text}



###############################################################################
## [SLM] STATE & LOG MANAGEMENT
###############################################################################

# @TO_DELETE: Potentially dead code
# create and save new StateLog entry in database
# def log_state(newstate):
#     pvs = m.ParVal.objects.filter(state=newstate)
#     for pv in pvs:
#         try:
#             oldlog = m.StateLog.objects.get(
#                     is_current=True,
#                     cap=newstate.cap,
#                     dev=newstate.dev,
#                     param=pv.par
#                     )
#             # if no update, continue
#             if oldlog.val == pv.val:
#                 continue

#             oldlog.is_current=False
#             oldlog.save()
#         except m.StateLog.DoesNotExist:
#             pass

#         newlog = m.StateLog(
#                 is_current=True,
#                 cap=newstate.cap,
#                 dev=newstate.dev,
#                 param=pv.par,
#                 val=pv.val
#                 )
#         newlog.save()

# get current state of dev/cap pair
def current_state(dev,cap):
    try:
        curstate = m.State.objects.get(cap=cap,dev=dev,action=False)
        return curstate
    except m.State.DoesNotExist:
        return None

# get value of state of dev/cap pair at a given time
def historical_state(dev,cap,targettime):
    state = m.State.objects.get(dev=dev,cap=cap,action=False)
    out = []
    for pv in m.ParVal.objects.filter(state=state):
        try:
            logs = m.StateLog.objects.filter(
                    status__in=[m.StateLog.HAPPENED, m.StateLog.CURRENT],
                    cap=state.cap,
                    dev=state.dev,
                    param=pv.par,
                    timestamp__lte=targettime
                )
            if logs:
                lastlog = max(logs,key=lambda log : log.timestamp)
                out.append((lastlog.param,lastlog.value))
            else:
                out.append((pv.par.id,"N/A"))
        except m.StateLog.DoesNotExist:
            out.append((pv.par.id,"N/A"))

    return out

# get record of all logged changes to a dev/cap pair
def device_cap_history(dev,cap):
    qset = m.StateLog.objects.filter(status=m.StateLog.HAPPENED,dev=dev,cap=cap)
    states = []
    for entry in sorted(qset,key=lambda entry : entry.timestamp,reverse=True):
        states.append((entry.timestamp.ctime(),entry.param.id,entry.value))
    return states


###############################################################################
## [DM] DEVICE MANAGEMENT
###############################################################################

def prep_command(action, group):
    '''
    Preparing the commands that will be sent to IoTCore

    Input:

    Output:
    '''
    if group == 'st':
        cap = action.cap
        pvs = m.ActionParVal.objects.filter(state=action)
        pars = [pv.par for pv in pvs]
        enumcommands = filter(lambda x: pv.par.is_command,pvs) #this shouldn't return >1
        if enumcommands:
            commname = enumcommands[0].par.sysname
            commvals = []
        else:
            commname = None #cap.commandname
            commvals = [{'name' : pv.par.name, 'value' : pv.val} for pv in pvs]
        return {'command'   : {'name' : commname,
                               'vals' : commvals}}
    else:
        return None

def send_command(command, group):
    if group == 'st':
        signed_command = {'signature' : 'superifttt',
                          'command' : command['command']}


def get_param_vals(param):
    if param.type == 'bin':
        param_val_list =  [param.binparam.tval, param.binparam.fval]
    elif param.type == 'set':
        options = m.SetParamOpt.objects.filter(param=param)
        param_val_list = [opt.value for opt in options]
    else:
        # TODO: should try to handle range/color
        # maybe we could use kmeans to cluster the values based on the past events?
        param_val_list = []
    return param_val_list


def get_param_vals_range(dev, cap, param):
    range_seps = m.RangeCounter.objects.filter(dev=dev, cap=cap, param=param, count__gt=0)
    return [rs.representative for rs in range_seps]


def get_param_vals_color(dev, cap, param):
    color_counts = m.ColorCounter.objects.filter(dev=dev, cap=cap, param=param, count__gt=0)
    return [cc.name for cc in color_counts]


def get_dev_commands(dev, trace, template_dict, boolean_map, orig_tap_list, plain_revert=False):
    """
    return a list of tuple (cap, param, value, count)
    """
    result = list()
    for cap in dev.caps.all():
        if cap.writeable:
            # this capability has commands
            # should iterate through all possible commands
            params = list(m.Parameter.objects.filter(cap=cap))
            if len(params) == 1:
                param = params[0]
                if param.type in ('set', 'bin'):
                    param_val_list = get_param_vals(param)
                elif param.type == 'range':
                    param_val_list = get_param_vals_range(dev, cap, param)
                elif param.type == 'color':
                    param_val_list = get_param_vals_color(dev, cap, param)
                else:
                    param_val_list = []
                for val in param_val_list:
                    entry = {
                        'device_name': dev.name,
                        'capability': cap.name,
                        'attribute': param.name,
                        'current_value': val
                    }
                    dev_name, cap_name, value = translateCapability(entry, template_dict=template_dict, boolean_map=boolean_map)
                    if type(value) == int or type(value) == float:
                        value = str(value)
                    elif type(value) == bool:
                        value = 'true' if value else 'false'
                    else:
                        value = value
                    target_action = dev_name + '.' + cap_name + '=' + str(value)
                    tap_list = [tap for tap in orig_tap_list if tap.action == target_action]
                    episode_list = extractEpisodes(trace, target_action, post_time_span=datetime.timedelta(minutes=2), consider_automated=True)
                    if not plain_revert:
                        _, revert_list = extractTriggerCases(trace, target_action, tap_list=tap_list)
                    else:
                        revert_time_list = extractRevertCases(trace, target_action)
                    count = len(episode_list)
                    covered = 0
                    for episode in episode_list:
                        if checkIfEpisodeCovered(episode, tap_list, target_action):
                            covered += 1
                    reverted = sum(revert_list) if not plain_revert else len(revert_time_list)
                    result.append((cap, param, val, count, covered, reverted))
            else:
                pass
            
    return result


def get_dev_caps(dev):
    """
    get all capabilities of a device
    """
    result = list()
    for cap in dev.caps.all():
        params = list(m.Parameter.objects.filter(cap=cap))
        result.append((cap, params))
            
    return result


#######################
# Permission Checking #
#######################

def is_error(status_code):
    return status_code >=400

def has_access_to_location(user, loc_id):
    if user.is_superuser:
        return True
    else:
        return m.Location.objects.filter(pk=loc_id, users=user).exists()

def check_access_to_location(request, loc_id: int):
    '''
    Given a request (which contains the user) and a location id, check:
        1. if the user has a loc token in the session
        2. if the location exists
        3. if location id corresponds
    Input:
        request: Django's request object
        loc_id:  the id of the location、
    Output:
        err_json: (dict) {"err": "xxxxx"}, defaults to {}, which means no error detected
        status:   (int) the status number, defaults to 200, which means no error detected
    '''
    err_msg = {}
    status = 200
    if 'location_token' not in request.session:
        err_msg["err"] = "Please log in!"
        status = 401
    elif not m.Location.objects.filter(token=request.session['location_token']).exists():
        err_msg["err"] = "The requested location doesn't exist."
        status = 404
    else:
        loc = m.Location.objects.get(token=request.session['location_token'])
        if loc.id != loc_id:
            err_msg["err"] = "The requested location doesn't correspond to the token."
            status = 400
    
    return err_msg, status


############
# Recorder #
############
def record_request(req_dict, typ, location):
    req_str = json.dumps(req_dict)
    return m.Record.objects.create(request=req_str, response="", typ=typ, location=location)


def record_response(res_dict, typ, location):
    res_str = json.dumps(res_dict)
    m.Record.objects.create(request="", response=res_str, typ=typ, location=location)


def get_location_from_user(user):
    locations = m.Location.objects.all()
    for loc in locations:
        if user in list(loc.users.all()):
            return loc
    return None


##########
# Helper #
##########

def get_error_msg(func_name, err, status=500):
    err_msg = "{}: {}\n{}".format(func_name, err, traceback.format_exc())
    m.ErrorLog.objects.create(err=err_msg)
    return {"msg": "{}".format(err)}

def get_now():
    return timezone.now() if settings.USE_TZ else datetime.datetime.now()
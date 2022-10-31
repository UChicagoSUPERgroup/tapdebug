### django modules
from json.decoder import JSONDecodeError
from django.core.exceptions import MultipleObjectsReturned
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.template import loader
from . import models as m
from django.db.models import Q
from django.core import serializers
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.conf import settings
from django.core.cache import cache, caches
from django.utils.crypto import get_random_string

### python modules
import operator as op
import datetime, random, json, re, datetime
import traceback
import pytz

### project moduels
from . import models as m
from . import capmap
from backend.util import *
from backend.translator import trigger_to_clause, action_to_clause, time_to_int, int_to_time, clause_to_trigger, \
    clause_to_action, trigger_to_homeio_clause, action_to_homeio_clause, homeio_info_to_dev_cap_param, homeio_val_to_val
from autotap.util import initialize_trace_for_location, get_trace_for_location, generate_dict_from_state_log, initialize_trace_from_log_list
from autotap.variable import generate_all_device_templates, generate_boolean_map
from autotap.translator import translate_rule_into_autotap_tap, pv_clause_to_autotap_statement, generate_cap_time_list_from_tap, \
    get_text_for_command
from autotapta.model.Trace import enhanceTraceWithTiming

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

# log in to a location from the login page
def fe_login(request):
    try:
        token = request.POST['token']
        
        try:
            location = m.Location.objects.get(token=token)
            request.session['location_token'] = token
        except m.Location.DoesNotExist:
            return JsonResponse({"msg": "Location not found for token" + token}, status=404)
        
        return JsonResponse({
            "locid": location.id, 
            "mode": location.user.mode if not location.is_template else m.User.CONTROL
        }, status=200)

    except Exception as e:
        return JsonResponse({"msg": repr(e)}, status = 500)

# log out from a location
def fe_logout(request):
    try:
        # @TODO: Should we remove access token and refresh token as well?
        logout(request)
        if 'location_token' in request.session:
            del request.session['location_token']
        return JsonResponse({}, status=200)
    except Exception as e:
        return JsonResponse({"msg": repr(e)}, status = 500)

def fe_get_loc_token(request):
    try:
        if 'location_token' not in request.session:
            return JsonResponse({"msg": "Please log in!"}, status=401)
        elif not m.Location.objects.filter(token=request.session['location_token']).exists():
            return JsonResponse({"msg": "The requested location doesn't exist."}, status=404)
        else:
            location = m.Location.objects.get(token=request.session['location_token'])
            resp = {
                "token": request.session['location_token'], 
                "locid": location.id,
                "mode": location.user.mode if not location.is_template else request.session['mode'], 
                "superuser": request.user.is_superuser
            }
            return JsonResponse(resp, status=200)
    except Exception as e:
        return JsonResponse({"msg": repr(e)}, status = 500)

def fe_get_devices(request):
    '''
    Get user's devices that are installed in a specific location. Create one if not exists.
    Input:
        - locid: location id in this project
    Output:
        - 200: {
            "devs": [
                {"id": "", "name": "", "icon": "", "mainState": True, "mainStateLabel": "On", "subscribed": True},
                ...
            ]
        }
        - others: {"msg": err_msg}
    '''
    kwargs = json.loads(request.body.decode('utf-8'))
    loc_id = kwargs["locid"]
    err_json, status = check_access_to_location(request, loc_id)
    if is_error(status):
        return JsonResponse(err_json, status=status)
    
    loc = m.Location.objects.get(id=loc_id)
    devs = m.Device.objects.filter(hidden=False)

    output = {"devs": []}
    
    template_dict = generate_all_device_templates()
    boolean_map = generate_boolean_map()
    trace = get_trace_for_location(loc)
    rule_set = m.Rule.objects.filter(location=loc).order_by('id')
    orig_tap_list = [translate_rule_into_autotap_tap(rule, use_tick_header=False) for rule in rule_set]
    cap_time_list = []
    for tap in orig_tap_list:
        cap_time_list += generate_cap_time_list_from_tap(tap)
    cap_time_list = list(set(cap_time_list))
    trace = enhanceTraceWithTiming(trace, cap_time_list, '*')

    for dev in devs:
        # check to see if the device has the power on/off capability
        has_switch_state = dev.caps.filter(name="Power On/Off").exists()
        new_entry = {
            "id": dev.id,
            "name": dev.name,
            "zone": {"id": dev.zone.id, "name": dev.zone.name},
            "icon": dev.icon
        }
        commands = list()
        # get all commands that can potentially be automatic if needed
        if 'get_commands' in kwargs and kwargs['get_commands']:
            plain_revert = 'plain_revert' in kwargs and kwargs['plain_revert']
            command_tup_list = get_dev_commands(dev, trace=trace, template_dict=template_dict, boolean_map=boolean_map, 
                                                orig_tap_list=orig_tap_list, plain_revert=plain_revert)
            for cap, param, val, count, covered, reverted in command_tup_list:
                command = {
                    "capability": {"id": cap.id, "name": cap.name, "label": cap.commandlabel}, 
                    "parameter": {"id": param.id, "name": param.name, "type": param.type, "values": get_param_vals(param)}, 
                    "value": val, "count": count, "covered": covered, 'reverted': reverted
                }
                commands.append(command)
        new_entry["commands"] = commands
        # get all capabilities
        capabilities = [
            {
                "id": cap.id, "name": cap.name, "label": cap.commandlabel, 
                "parameters": [{
                    "id": param.id, "name": param.name, "type": param.type, "values": get_param_vals(param)
                } for param in params]
            } for cap, params in get_dev_caps(dev)]
        new_entry["capabilities"] = capabilities

        if has_switch_state:
            try:
                curr_state = m.StateLog.objects.get(dev=dev, cap__name="Power On/Off", status=m.StateLog.CURRENT)
                new_entry["mainState"] = curr_state.value.lower() == "on"
                new_entry["mainStateLabel"] = curr_state.value
            except m.StateLog.DoesNotExist:
                new_entry["mainState"] = None
                new_entry["mainStateLabel"] = None
            except m.StateLog.MultipleObjectsReturned:
                all_related_states = m.StateLog.objects.filter(
                    dev=dev, 
                    cap__name="Power On/Off", 
                    status=m.StateLog.CURRENT
                ).order_by("-timestamp")

                # mark all older states as HAPPENED
                for state in all_related_states[1:]:
                    state.status = m.StateLog.HAPPENED
                m.StateLog.objects.bulk_update(all_related_states[1:], ['status'])

                # use the most recent state as the current state
                curr_state = all_related_states[0]
                new_entry["mainState"] = curr_state.value.lower() == "on"
                new_entry["mainStateLabel"] = curr_state.value
        else:
            new_entry["mainState"] = None
            new_entry["mainStateLabel"] = None
        output["devs"].append(new_entry)

    for dev_clause in output["devs"]:
        for command_clause in dev_clause["commands"]:
            command_text = get_text_for_command(command_clause, dev_clause)
            command_clause['text'] = command_text
    return JsonResponse(output, status=200)

def fe_get_user(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    u = get_or_make_user(kwargs['code'],kwargs['mode'])
    json_resp = {'userid' : u.id}
    return JsonResponse(json_resp)


def fe_all_rules_helper(loc_id):
    # helper function without checking identity
    json_resp = {'rules' : []}

    location = m.Location.objects.get(id=loc_id)
    
    rule_set = m.Rule.objects.filter(location=location).order_by('id')
    
    for rule in rule_set:
        if rule.type == 'es':
            ifclause = []
            t = rule.esrule.Etrigger
            ifclause.append({'channel' : {'icon' : t.chan.icon if t.chan else ''},
                             'text' : t.text})
            for t in sorted(rule.esrule.Striggers.all(),key=lambda x: x.pos):
                ifclause.append({'channel' : {'icon' : t.chan.icon if t.chan else ''},
                                 'text' : t.text})
            a = rule.esrule.action
            thenclause = [{'channel' : {'icon' : a.chan.icon if not (a.chan == None) else ''},
                           'text' : a.text}]

            json_resp['rules'].append({'id' : rule.id,
                                       'ifClause' : ifclause,
                                       'thenClause' : thenclause,
                                       'temporality' : 'event-state'})
    json_resp['loc_id'] = loc_id

    return json_resp


# FRONTEND VIEW
#@csrf_exempt
def fe_all_rules(request):
    '''
    Get all the rules that belong to a location\n
    Input:
        request:    Django's request object
        loc_id:     the id of the location
    Output:
        (JsonResponse) {"rules": [...]}
    '''
    
    try:
        location_token = request.session['location_token']
        location = m.Location.objects.get(token=location_token)
        loc_id = location.id
    except Exception as e:
        return JsonResponse({"msg": str(e)}, status=500)
    
    json_resp = fe_all_rules_helper(loc_id)
    if location.is_template:
        json_resp['mode'] = request.session['mode']
    else:
        json_resp['mode'] = location.user.mode
    return JsonResponse(json_resp)


#@csrf_exempt
def fe_get_full_rule(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    json_resp = {}

    ### error handling
    err_json, status = check_access_to_location(request, kwargs['loc_id'])
    if is_error(status):
        return JsonResponse(err_json, status=status)
    ##################

    rule = m.Rule.objects.get(id=kwargs['ruleid'])

    if rule.type == 'es':
        rule = rule.esrule
        ifclause = []
        t = rule.Etrigger
        ifclause.append(trigger_to_clause(t,True))
        for t in sorted(rule.Striggers.all(),key=lambda x: x.pos):
            ifclause.append(trigger_to_clause(t,False))

        a = rule.action
        thenclause = action_to_clause(a)

        json_resp['rule'] = {'id' : rule.id,
                             'ifClause' : ifclause,
                             'thenClause' : [thenclause],
                             'temporality' : 'event-state'}

    return JsonResponse(json_resp)

### @TO_DELETE: Potentially dead code
# combined call of all_devs and all_chans
# NOT IN USE
# def fe_all_devs_and_chans(request):
#     kwargs = request.POST
#     user = m.User_ICSE19.objects.get(id=kwargs['userid'])
#     json_resp = {}
#     json_resp['devs'] = all_devs(user)
#     json_resp['chans'] = all_chans(user)
#     return JsonResponse(json_resp)

# FRONTEND VIEW
# let frontend get csrf cookie
@ensure_csrf_cookie
def fe_get_cookie(request):
    return JsonResponse({})

# FRONTEND VIEW
# gets all of a user's channels
#@csrf_exempt
def fe_all_chans(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    if not request.user.is_authenticated:
        return JsonResponse({}, status=401)

    json_resp = valid_chans(request.user,kwargs['is_trigger'])
    return JsonResponse(json_resp)

# FRONTEND VIEW
# gets all zones
#@csrf_exempt
def fe_all_zones(request):
    kwargs = json.loads(request.body.decode('utf-8'))

    json_resp = {'zones' : []}
    json_resp['zones'] = [{'id': zone.id, 'name': zone.name} for zone in m.Zone.objects.all()]

    return JsonResponse(json_resp)

# FRONTEND VIEW
# return id:name dict of all devices with a given channel
#@csrf_exempt
def fe_devs_with_chan(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    if not request.user.is_authenticated:
        return JsonResponse({}, status=401)
    devs = m.Device.objects.filter(Q(users__in=[request.user])).distinct().order_by('name')
    chan = m.Channel.objects.get(id=kwargs['channelid'])
    devs = filter(lambda x : dev_has_valid_cap(x,chan,kwargs['is_trigger']),devs)
    json_resp = {'devs' : []}
    for dev in devs:
        json_resp['devs'].append({'id' : dev.id,'name' : dev.name})
    return JsonResponse(json_resp)

# return id: name dict of all devices within a given location
def fe_devs_with_loc(request):
    kwargs = json.loads(request.body.decode('utf-8'))

    err_json, status = check_access_to_location(request, kwargs['loc_id'])
    if is_error(status):
        return JsonResponse(err_json, status=status)

    zone_id = kwargs['zone_id']

    devs = m.Device.objects.filter(zone__id=zone_id).order_by('name')
    
    devs = filter(lambda x : dev_has_valid_cap_no_channel(x, kwargs['is_trigger']), devs)
    json_resp = {'devs' : []}
    for dev in devs:
        json_resp['devs'].append({'id' : dev.id,'name' : dev.name})
    return JsonResponse(json_resp)

# return id:name dict of all channels with a given device
# NOT IN USE
def fe_chans_with_dev(request,**kwargs):
    chans = m.Channel.objects.filter(capability__device__id=kwargs['deviceid'])
    json_resp = {}
    for chan in chans:
        json_resp[chan.id] = chan.name

    return JsonResponse(json_resp)

### @TO_DELETE: Potentially dead code
# return id:name dict of all capabilities for a given dev/chan pair
# NOT IN USE
# def fe_get_all_caps(request,**kwargs):
#     caps = m.Capability.objects.filter(channels__id=kwargs['channelid'],device__id=kwargs['deviceid'])
#     json_resp = {}
#     for cap in caps:
#         json_resp[cap.id] = cap.name
#     return JsonResponse({'caps' : json_resp})

# FRONTEND VIEW
# return id:name dict of contextually valid capabilities for a given dev/chan pair
#@csrf_exempt
def fe_get_valid_caps(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    caps = m.Capability.objects.filter(channels__id=kwargs['channelid'],device__id=kwargs['deviceid']).order_by('name')

    json_resp = {'caps' : []}
    for id,name,label,timelabel in filtermap_caps(caps,kwargs['is_trigger'],kwargs['is_event']):
        json_resp['caps'].append({'id' : id, 'name' : name, 'label' : label, 'timelabel': timelabel})
    return JsonResponse(json_resp)

# return capabilities without considering channel
def fe_get_valid_caps_with_loc(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    caps = m.Capability.objects.filter(device__id=kwargs['deviceid']).order_by('name')

    json_resp = {'caps' : []}
    for id,name,label,timelabel in filtermap_caps(caps,kwargs['is_trigger'],kwargs['is_event']):
        json_resp['caps'].append({'id' : id, 'name' : name, 'label' : label, 'timelabel': timelabel})
    return JsonResponse(json_resp)

# return id:(type,val constraints) dict of parameters for a given cap
#@csrf_exempt
def fe_get_params(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    cap = m.Capability.objects.get(id=kwargs['capid'])
    json_resp = {'params' : []}
    for param in m.Parameter.objects.filter(cap_id=kwargs['capid']).order_by('id'):
        if param.type == 'set':
            json_resp['params'].append({'id' : param.id,
                                        'name' : param.name,
                                        'type' : "set",
                                        'values' : [opt.value for opt in m.SetParamOpt.objects.filter(param_id=param.id)]})
        elif param.type == 'range':
            json_resp['params'].append({'id' : param.id,
                                        'name' : param.name,
                                        'type' : 'range',
                                        'values' : [param.rangeparam.min,param.rangeparam.max,param.rangeparam.interval]})
        elif param.type == 'bin':
            json_resp['params'].append({'id' : param.id,
                                        'name' : param.name,
                                        'type' : 'bin',
                                        'values' : [param.binparam.tval,param.binparam.fval]})
        elif param.type == 'input':
            json_resp['params'].append({'id' : param.id,
                                        'name' : param.name,
                                        'type' : 'input',
                                        'values' : [param.inputparam.inputtype]})
        elif param.type == 'time':
            json_resp['params'].append({'id' : param.id,
                                        'name' : param.name,
                                        'type' : 'time',
                                        'values' : [param.timeparam.mode]})
        elif param.type == 'duration':
            json_resp['params'].append({'id' : param.id,
                                        'name' : param.name,
                                        'type' : 'duration',
                                        'values' : [param.durationparam.maxhours,param.durationparam.maxmins,param.durationparam.maxsecs]})
        elif param.type == 'color':
            json_resp['params'].append({'id' : param.id,
                                        'name' : param.name,
                                        'type' : 'color',
                                        'values' : [param.colorparam.mode]})
        elif param.type == 'meta':
            json_resp['params'].append({'id' : param.id,
                                        'name' : param.name,
                                        'type' : 'meta',
                                        'values' : [param.metaparam.is_event]})
    return JsonResponse(json_resp)



###############################################################################
## [RC] RULE CREATION
###############################################################################

def fe_create_esrule_helper(kwargs, user, forcecreate=False):
    # Error checking
    loc_id = kwargs['loc_id']
    try:
        location = m.Location.objects.get(pk=loc_id)
    except m.Location.DoesNotExist:
        return JsonResponse({}, status=404)

    ruleargs = kwargs['rule']
    ifclause = ruleargs['ifClause']
    
    event = ifclause[0]
    action_c = ruleargs['thenClause'].pop()

    e_trig = clause_to_trigger(event)
    a_state = clause_to_action(action_c)

    if kwargs['mode'] == "create" or forcecreate==True:
        rule = m.ESRule(location=location,
                        type='es',
                        Etrigger=e_trig,
                        action=a_state)
        rule.save()
    else: #edit existing rule
        try:
            rule = m.ESRule.objects.get(id=kwargs['rule_id'])
        except m.ESRule.DoesNotExist:
            return fe_create_esrule_helper(kwargs, user, forcecreate=True)

        orig_e_trig = rule.Etrigger
        orig_action = rule.action

        rule.Etrigger=e_trig
        rule.action=a_state
        rule.save()

        orig_e_trig.delete()
        orig_action.delete()

        for st in rule.Striggers.all():
            rule.Striggers.remove(st)
            st.delete()

    try:
        for state in ifclause[1:]:
            s_trig = clause_to_trigger(state)
            rule.Striggers.add(s_trig)
    except IndexError:
        pass

    return JsonResponse({}, status=201)


# create (OR EDIT) Event State Rule
#@csrf_exempt
def fe_create_esrule(request, forcecreate=False):
    kwargs = json.loads(request.body.decode('utf-8'))

    err_json, status = check_access_to_location(request, kwargs['loc_id'])
    if is_error(status):
        return JsonResponse(err_json, status=status)
    
    loc_id = kwargs['loc_id']
    try:
        location = m.Location.objects.get(pk=loc_id)
    except m.Location.DoesNotExist:
        return JsonResponse({}, status=404)

    user = request.user
    resp = fe_create_esrule_helper(kwargs, user, forcecreate=forcecreate)

    record_response(fe_all_rules_helper(loc_id), 'edit_rule', location)
    return resp


def fe_create_esrules(request):
    kwargs = json.loads(request.body.decode('utf-8'))

    # Error checking
    loc_id = kwargs['loc_id']
    try:
        location = m.Location.objects.get(pk=loc_id)
    except m.Location.DoesNotExist:
        return JsonResponse({}, status=404)

    err_json, status = check_access_to_location(request, kwargs['loc_id'])
    if is_error(status):
        return JsonResponse(err_json, status=status)
    
    user = request.user
    ruleargs = kwargs['rules']
    resp_list = []
    for rulearg in ruleargs:
        rule_id = rulearg['id'] if 'id' in rulearg else 0
        mode = 'edit' if rule_id else 'create'
        args = {'rule': rulearg, 'mode': mode, 'loc_id': loc_id, 'rule_id': rule_id}
        resp = fe_create_esrule_helper(args, user)
        resp_list.append(resp)
    
    for resp in resp_list:
        if resp.status_code != 201:
            return resp
    
    record_response(fe_all_rules_helper(loc_id), 'edit_rule', location)
    return JsonResponse({}, status=201)


def fe_change_esrules(request):
    kwargs = json.loads(request.body.decode('utf-8'))

    dev_c = kwargs['device']
    command_c = kwargs['command']

    target_dev = m.Device.objects.get(id=dev_c['id'])
    location = target_dev.location
    loc_id = location.id
    target_action = pv_clause_to_autotap_statement(dev_c, command_c['capability'], 
                                                command_c['parameter'], command_c['value'])

    rule_set = list(m.Rule.objects.filter(st_installed_app_id=location.st_installed_app_id).order_by('id'))
    orig_tap_list = [translate_rule_into_autotap_tap(rule, use_tick_header=False) for rule in rule_set]
    target_action = pv_clause_to_autotap_statement(dev_c, command_c['capability'], 
                                                command_c['parameter'], command_c['value'])
    orig_tap_id_list = [rule.id for tap, rule in zip(orig_tap_list, rule_set) if tap.action == target_action]

    user = request.user
    ruleargs = kwargs['rules']
    # resp_list = []
    # for rulearg in ruleargs:
    #     rule_id = rulearg['id'] if 'id' in rulearg else 0
    #     mode = 'edit' if rule_id else 'create'
    #     args = {'rule': rulearg, 'mode': mode, 'loc_id': loc_id, 'rule_id': rule_id}
    #     resp = fe_create_esrule_helper(args, user)
    #     resp_list.append(resp)
    resp_list = []

    modified_rule_id_set = {rule["id"] for rule in ruleargs if rule["id"]}
    for rule in rule_set:
        if rule.id in orig_tap_id_list:
            if rule.id not in modified_rule_id_set:
                # should delete this
                if not has_access_to_location(request.user, location.pk):
                    return JsonResponse({'rules' : []}, status=403)

                if rule.type == 'es':
                    rule.esrule.Etrigger.delete()
                    for st in rule.esrule.Striggers.all():
                        st.delete()
                    rule.esrule.action.delete()
                rule.delete()
            else:
                # should modify this
                target_arg = None
                for rulearg in ruleargs:
                    if rulearg["id"] == rule.id:
                        target_arg = rulearg
                        break
                
                if target_arg is not None:
                    rule_id = rulearg['id'] if 'id' in rulearg else 0
                    mode = 'edit' if rule_id else 'create'
                    args = {'rule': rulearg, 'mode': mode, 'loc_id': loc_id, 'rule_id': rule_id}
                    resp = fe_create_esrule_helper(args, user)
                    resp_list.append(resp)
        else:
            # not the same action, skip
            pass
    
    record_response(fe_all_rules_helper(loc_id), 'edit_rule', location)
    for resp in resp_list:
        if resp.status_code != 201:
            return resp
    return JsonResponse({}, status=201)


#@csrf_exempt
def fe_delete_rule(request):
    kwargs = json.loads(request.body.decode('utf-8'))

    try:
        loc = m.Location.objects.get(id=kwargs['locid'])
    except m.Location.DoesNotExist:
        return JsonResponse({'rules' : []}, status=404)

    try:
        rule = m.Rule.objects.get(id=kwargs['ruleid'])
    except m.Rule.DoesNotExist:
        return fe_all_rules(request)

    err_json, status = check_access_to_location(request, kwargs['locid'])
    if is_error(status):
        return JsonResponse(err_json, status=status)

    if rule.type == 'es':
        for st in rule.esrule.Striggers.all():
            st.delete()
        rule.esrule.Etrigger.delete()
        rule.esrule.action.delete()
    rule.delete()

    record_response(fe_all_rules_helper(loc.id), 'edit_rule', loc)
    return fe_all_rules(request)

## not functional
# def fe_create_ssrule(request,**kwargs):
#     priority = kwargs['priority']
#     action = m.State.objects.get(id=kwargs['actionid'])
#     rule = m.SSRule(action=action,priority=priority)
#     rule.save()

#     for val in kwargs['triggerids']:
#         rule.triggers.add(m.State.objects.get(id=val))

#     return JsonResponse({'ssruleid' : rule.id})

def fe_create_rule(request,**kwargs):
    if kwargs['temp'] == 'es':
        return fe_create_esrule(request,kwargs)
    else:
        return fe_create_ssrule(request,kwargs)



###############################################################################
## [SPC] SAFETY PROPERTY CREATION
###############################################################################

#@csrf_exempt
def fe_all_sps(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    json_resp = {'sps' : []}

    try:
        user = m.User_ICSE19.objects.get(id=kwargs['userid'])
    except KeyError:
        user = get_or_make_user(kwargs['code'],'sp')
        json_resp['userid'] = user.id

    sps = m.SafetyProp.objects.filter(owner=user,task=kwargs['taskid']).order_by('id')
    for sp in sps:
        if sp.type == 1:
            sp1 = sp.sp1
            triggers = sp1.triggers.all().order_by('pos')
            thisstate = triggers[0]
            try:
                thatstate = list(map(display_trigger,triggers[1:]))
            except IndexError:
                thatstate = []

            json_resp['sps'].append({'id' : sp.id,
                                     'thisState' : [display_trigger(thisstate)],
                                     'thatState' : thatstate,
                                     'compatibility' : sp1.always})
        elif sp.type == 2:
            sp2 = sp.sp2
            
            json2 = {'id' : sp.id,
                     'stateClause' : [display_trigger(sp2.state)],
                     'compatibility' : sp2.always}
            if sp2.comp:
                json2['comparator'] = sp2.comp
            if sp2.time != None:
                json2['time'] = int_to_time(sp2.time)
            
            clauses = sp2.conds.all().order_by('pos')
            if clauses != []:
                json2['alsoClauses'] = list(map(display_trigger,clauses))

            json_resp['sps'].append(json2)
        elif sp.type == 3:
            sp3 = sp.sp3
            json3 = {'id' : sp.id,
                     'triggerClause' : [display_trigger(sp3.event)],
                     'compatibility' : sp3.always}
            
            if sp3.comp:
                json3['comparator'] = sp3.comp
            if sp3.occurrences != None:
                json3['times'] = sp3.occurrences
            
            clauses = sp3.conds.all().order_by('pos')
            if clauses != []:
                json3['otherClauses'] = list(map(display_trigger,clauses))

            if sp3.time != None:
                if sp3.timecomp != None:
                    json3['afterTime'] = int_to_time(sp3.time)
                    json3['timeComparator'] = sp3.timecomp
                else:
                    json3['withinTime'] = int_to_time(sp3.time)

            json_resp['sps'].append(json3)

    return JsonResponse(json_resp)

#@csrf_exempt
def fe_get_full_sp(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    sp = m.SafetyProp.objects.get(id=kwargs['spid'])
    if sp.type == 1:
        return fe_get_full_sp1(request)
    elif sp.type == 2:
        return fe_get_full_sp2(request)
    elif sp.type == 3:
        return fe_get_full_sp3(request)

#@csrf_exempt
def fe_get_full_sp1(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    sp = m.SP1.objects.get(safetyprop_ptr_id=kwargs['spid'])
    ts = sp.triggers.all()
    thisstate = trigger_to_clause(ts[0],False)
    thatstate = []
    for t in ts[1:]:
        thatstate.append(trigger_to_clause(t,False))
    
    json_resp = {}
    json_resp['sp'] = {'thisState' : [thisstate],
                       'thatState' : thatstate,
                       'compatibility' : sp.always}

    return JsonResponse(json_resp)

#@csrf_exempt
def fe_get_full_sp2(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    sp = m.SP2.objects.get(safetyprop_ptr_id=kwargs['spid'])

    state = trigger_to_clause(sp.state,False)
    json_resp = {'sp' : {'stateClause' : [state],
                         'compatibility' : sp.always}}
    if sp.comp != None:
        json_resp['sp']['comparator'] = sp.comp

    if sp.time != None:
        json_resp['sp']['time'] = int_to_time(sp.time)

    conds = sp.conds.all()
    if conds != []:
        json_resp['sp']['alsoClauses'] = []
        for c in conds:
            json_resp['sp']['alsoClauses'].append(trigger_to_clause(c,False))

    return JsonResponse(json_resp)

#@csrf_exempt
def fe_get_full_sp3(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    sp = m.SP3.objects.get(safetyprop_ptr_id=kwargs['spid'])

    event = trigger_to_clause(sp.event,True)
    json_resp = {'sp' : {'triggerClause' : [event],
                         'compatibility' : sp.always}}

    if sp.occurrences != None and sp.comp != None:
        json_resp['sp']['comparator'] = sp.comp
        json_resp['sp']['times'] = sp.occurrences

    if sp.time != None:
        if sp.comp != None:
            json_resp['sp']['withinTime'] = int_to_time(sp.time)
        elif sp.timecomp != None:
            json_resp['sp']['afterTime'] = int_to_time(sp.time)
            json_resp['sp']['timeComparator'] = sp.timecomp

    conds = sp.conds.all()
    if conds != []:
        json_resp['sp']['otherClauses'] = []
        for c in conds:
            json_resp['sp']['otherClauses'].append(trigger_to_clause(c,False))

    return JsonResponse(json_resp)

#@csrf_exempt
def fe_delete_sp(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    sp = m.SafetyProp.objects.get(id=kwargs['spid'])

    if sp.type == 1:
        sp = sp.sp1
        for t in sp.triggers.all():
            t.delete()
    elif sp.type == 2:
        sp = sp.sp2
        sp.state.delete()
        for c in sp.conds.all():
            c.delete()
    elif sp.type == 3:
        sp = sp.sp3
        sp.event.delete()
        for c in sp.conds.all():
            c.delete()

    sp.delete()

    return fe_all_sps(request)

#@csrf_exempt
def fe_create_sp1(request,forcecreate=False):
    kwargs = json.loads(request.body.decode('utf-8'))
    spargs = kwargs['sp']

    if kwargs['mode'] == 'create' or forcecreate == True:
        sp = m.SP1(owner=m.User_ICSE19.objects.get(id=kwargs['userid']),
                   task=kwargs['taskid'],
                   type=1,
                   always=spargs['compatibility'])
        sp.save()
    else: #edit sp
        try:
            sp = m.SafetyProp.objects.get(id=kwargs['spid'])
        except m.SafetyProp.DoesNotExist: # catch non-existent SP error
            return fe_create_sp1(request,forcecreate=True)

        sp = sp.sp1

        sp.always = spargs['compatibility']
        sp.save()
        for trig in sp.triggers.all():
            sp.triggers.remove(trig)

    for clause in ([spargs['thisState'][0]] + spargs['thatState']):
        t = clause_to_trigger(clause)
        sp.triggers.add(t)

    sp.save()
    return JsonResponse({})

#@csrf_exempt
def fe_create_sp2(request,forcecreate=False):
    kwargs = json.loads(request.body.decode('utf-8'))
    spargs = kwargs['sp']

    clause = spargs['stateClause'][0]
    t = clause_to_trigger(clause)

    if kwargs['mode'] == 'create' or forcecreate==True:
        sp = m.SP2(owner=m.User_ICSE19.objects.get(id=kwargs['userid']),
                          task=kwargs['taskid'],
                          type=2,
                          always=spargs['compatibility'],
                          state = t)
        sp.save()
    else:
        try:
            sp = m.SafetyProp.objects.get(id=kwargs['spid'])
        except m.SafetyProp.DoesNotExist:
            return fe_create_sp2(request,forcecreate=True)

        sp = sp.sp2

        sp.always = spargs['compatibility']
        sp.state = t
        sp.save()

        # null out remaining fields
        for cond in sp.conds.all():
            sp.conds.remove(cond)
        sp.comp = None
        sp.time = None
        sp.save()

    try:
        comp = spargs['comparator']
        time = spargs['time']
        time = time_to_int(time)
        if time > 0:
            sp.comp = comp
            sp.time = time
            sp.save()
        else:
            pass
    except KeyError:
        pass

    try:
        clauses = spargs['alsoClauses']
        for clause in clauses:
            t = clause_to_trigger(clause)
            sp.conds.add(t)
    except KeyError:
        pass

    sp.save()
    
    return JsonResponse({})

#@csrf_exempt
def fe_create_sp3(request,forcecreate=False):
    kwargs = json.loads(request.body.decode('utf-8'))
    spargs = kwargs['sp']

    event = spargs['triggerClause'][0]
    t = clause_to_trigger(event)

    if kwargs['mode'] == 'create' or forcecreate==True:
        sp = m.SP3(owner=m.User_ICSE19.objects.get(id=kwargs['userid']),
                   task=kwargs['taskid'],
                   type=3,
                   always=spargs['compatibility'],
                   event = t)
        sp.save()
    else:
        try:
            sp = m.SafetyProp.objects.get(id=kwargs['spid'])
        except m.SafetyProp.DoesNotExist:
            return fe_create_sp3(request,forcecreate=True)

        sp = sp.sp3

        sp.always = spargs['compatibility']
        sp.event = t
        sp.save()

        # null out other fields
        for cond in sp.conds.all():
            sp.conds.remove(cond)
        sp.comp = None
        sp.occurrences = None
        sp.time = None
        sp.timecomp = None
        sp.save()

    try:
        comp = spargs['comparator']
        times = spargs['times']
        if times > 0:
            sp.comp = comp
            sp.occurrences = times
            try:
                within = spargs['withinTime']
                sp.time = time_to_int(within)
            except KeyError:
                pass
        else:
            pass
    except KeyError:
        pass

    try:
        clauses = spargs['otherClauses']
        for clause in clauses:
            t = clause_to_trigger(clause)
            sp.conds.add(t)
    except KeyError:
        pass

    try:
        time = spargs['afterTime']
        timecomp = spargs['timeComparator']
        sp.time=time_to_int(time)
        sp.timecomp=timecomp
    except KeyError:
        pass

    sp.save()
    return JsonResponse({})



###############################################################################
## [SLM] STATE & LOG MANAGEMENT
###############################################################################

# get current state of all caps of a device
def fe_current_device_status(request,**kwargs):
    dev = m.Device.objects.get(id=kwargs['deviceid'])
    json = {}
    for cap in dev.caps.all():
        state = current_state(dev,cap)
        if state != None:
            json[cap.id] = []
            for pv in m.ParVal.objects.filter(state=state):
                json[cap.id].append((pv.par.id,pv.val))
        else:
            json[cap.id] = "N/A"

    return JsonResponse(json)

# get state of all caps of a device [timedelta] minutes ago
def fe_historical_device_status(request,**kwargs):
    dev = m.Device.objects.get(id=kwargs['deviceid'])
    targettime = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=kwargs['timedelta'])

    json = {
        "device_name" : dev.name
        }

    for cap in dev.caps.all():
        capstate = historical_state(dev,cap,targettime)
        json[cap.id] = capstate

    return JsonResponse(json)

# get record of all logged changes to a device
def fe_device_history(request,**kwargs):
    dev = m.Device.objects.get(id=kwargs['deviceid'])
    qset = m.StateLog.objects.filter(state__dev_id=dev.id)
    json = {"history" : []}
    for entry in sorted(qset,key=lambda entry : entry.timestamp,reverse=True):
        json["history"].append((entry.timestamp.ctime(),entry.param.id,entry.value))

    return JsonResponse(json)

# get status of monitored device status
# check if we can proceed the survey
def fe_get_monitored_dev_status(request):
    kwargs = json.loads(request.body.decode('utf-8'))

    # Error checking
    loc_id = kwargs['loc_id']

    try:
        location = m.Location.objects.get(pk=loc_id)
    except m.Location.DoesNotExist:
        return JsonResponse({}, status=404)

    err_json, status = check_access_to_location(request, kwargs['loc_id'])
    if is_error(status):
        return JsonResponse(err_json, status=status)
    
    dev_monitors = m.DeviceMonitor.objects.filter(loc=location)
    
    proceed = True
    for dev_monitor in dev_monitors:
        if dev_monitor.value != dev_monitor.target:
            proceed = False
            break

    json_resp = {'proceed': proceed, 'pending_trace': location.pending_trace}
    return JsonResponse(json_resp, status=200)

# get info needed for the frontend given a certain scenario/task
# should update User's current scenario if needed
def fe_get_scenario_info(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    json_resp = {}
    try:
        stage = kwargs['stage']
        user_code = kwargs['usercode']
        task_id = kwargs['taskid']
        # get the corresponding location
        if stage == 't':
            location = m.Location.objects.get(
                scenario__stage=stage, scenario__task=task_id, is_template=True)
        else:
            location = m.Location.objects.get(
                scenario__stage=stage, scenario__task=task_id, user__code=user_code)
        json_resp['loc_token'] = location.token
        json_resp['loc_id'] = location.id
        # log the user into this location
        request.session['location_token'] = location.token
        
        # update user stage
        user = m.User.objects.get(code=user_code)
        json_resp['user_mode'] = user.mode
        scenario = m.Scenario.objects.get(stage=stage, task=task_id)
        user.currentscenario = scenario
        user.save()

        # log the user mode here
        request.session['mode'] = user.mode

        # fetch required data for page
        #   get rules for the location
        rules = m.ESRule.objects.filter(location=location)
        rules_frontend = []
        for rule in rules:
            ifclause = []
            t = rule.Etrigger
            ifclause.append(trigger_to_clause(t,True))
            for t in sorted(rule.Striggers.all(),key=lambda x: x.pos):
                ifclause.append(trigger_to_clause(t,False))

            a = rule.action
            thenclause = action_to_clause(a)

            rules_frontend.append({'id' : rule.id,
                'ifClause' : ifclause,
                'thenClause' : [thenclause],
                'temporality' : 'event-state'})
        json_resp['rules'] = rules_frontend

        # get scenario pages
        pages = m.ScenarioPage.objects.filter(scenario=scenario).order_by('position')
        pages_frontend = []
        for page in pages:
            if not page.isexperience:
                pages_frontend.append({
                    'position': page.position,
                    'text': page.text,
                    'image': page.image,
                    'title': page.title,
                    'needcondition': page.needcondition,
                    'showrules': page.showrules})
        json_resp['pages'] = pages_frontend

    except Exception as e:
        error_json = get_error_msg('fe_get_scenario_info', e)
        return JsonResponse(error_json, status = 500)
    
    return JsonResponse(json_resp, status=200)


def fe_upload_trace(request):
    # this function set 'pending_trace' flag in location
    kwargs = json.loads(request.body.decode('utf-8'))
    json_resp = {}
    try:
        loc_id = kwargs['loc_id']
        location = m.Location.objects.get(id=loc_id)
        if not location.is_template:
            location.pending_trace = True
            location.save()
    except Exception as e:
        error_json = get_error_msg('fe_upload_trace', e)
        return JsonResponse(error_json, status = 500)
    
    return JsonResponse(json_resp, status=200)


###############################################################################
## [HIO] CONNECTIONS WITH HOME IO
###############################################################################

def hio_all_rules(request):
    token = request.GET.get("token")
    try:
        location = m.Location.objects.get(token=token)
    except m.Location.DoesNotExist as e:
        return JsonResponse({"msg": repr(e)}, status = 404)
    
    json_resp = {'rules' : []}
    
    rule_set = m.Rule.objects.filter(location=location).order_by('id')
    
    for rule in rule_set:
        if rule.type == 'es':
            # TODO: timing trigger is not supported yet
            t = rule.esrule.Etrigger
            try:
                trigger = trigger_to_homeio_clause(t)
            except Exception as e:
                return JsonResponse({"msg": repr(e)}, status = 500)

            conditions = []
            for t in sorted(rule.esrule.Striggers.all(),key=lambda x: x.pos):
                try:
                    condition = trigger_to_homeio_clause(t)
                except Exception as e:
                    return JsonResponse({"msg": repr(e)}, status = 500)
                conditions.append(condition)
            
            a = rule.esrule.action
            try:
                action = action_to_homeio_clause(a)
            except Exception as e:
                error_json = get_error_msg('hio_get_rules_and_devs', e)
                return JsonResponse(error_json, status = 500)
    
            json_resp['rules'].append({'id' : rule.id,
                                       'trigger' : trigger,
                                       'conditions' : conditions,
                                       'action' : action})

    return JsonResponse(json_resp)


def hio_get_monitored_devs(request):
    token = request.GET.get("token")
    try:
        location = m.Location.objects.get(token=token)
    except m.Location.DoesNotExist as e:
        return JsonResponse({"msg": repr(e)}, status = 404)

    # get all monitored devices
    devs = m.DeviceMonitor.objects.filter(loc=location)

    # for each one, generate the homeio representation
    json_resp = {'devs': []}
    for mon_dev in devs:
        dev_homeio = {
            'typ': mon_dev.dev.typ,
            'data_typ': mon_dev.dev.data_typ,
            'address': mon_dev.dev.address,
            'name': mon_dev.dev.name
        }
        json_resp['devs'].append(dev_homeio)
    
    return JsonResponse(json_resp)


def hio_get_rules_and_devs(request):
    try:
        user_code = request.GET.get("user_code")
        user = m.User.objects.get(code=user_code)
        try:
            location = m.Location.objects.get(user=user, scenario=user.currentscenario)
        except m.Location.DoesNotExist:
            return JsonResponse({'devs': [], 'rules': [], 'loc_token': None, 'pending_trace': False})

        json_resp = {'devs': [], 'rules': [], 'loc_token': location.token, 'pending_trace': location.pending_trace}
        # step 1: get all monitored devices
        devs = m.DeviceMonitor.objects.filter(loc=location)
        for mon_dev in devs:
            dev_homeio = {
                'typ': mon_dev.dev.typ,
                'data_typ': mon_dev.dev.data_typ,
                'address': mon_dev.dev.address,
                'name': mon_dev.dev.name
            }
            json_resp['devs'].append(dev_homeio)
        
        # step 2: get all rules
        rule_set = m.Rule.objects.filter(location=location).order_by('id')
        for rule in rule_set:
            if rule.type == 'es':
                # TODO: timing trigger is not supported yet
                t = rule.esrule.Etrigger
                try:
                    trigger = trigger_to_homeio_clause(t)
                except Exception as e:
                    return JsonResponse({"msg": repr(e)}, status = 500)

                conditions = []
                for t in sorted(rule.esrule.Striggers.all(),key=lambda x: x.pos):
                    try:
                        condition = trigger_to_homeio_clause(t)
                    except Exception as e:
                        return JsonResponse({"msg": repr(e)}, status = 500)
                    conditions.append(condition)
                
                a = rule.esrule.action
                try:
                    action = action_to_homeio_clause(a)
                except Exception as e:
                    return JsonResponse({"msg": repr(e)}, status = 500)
        
                json_resp['rules'].append({'id' : rule.id,
                                        'trigger' : trigger,
                                        'conditions' : conditions,
                                        'action' : action})
        
        return JsonResponse(json_resp)
    except Exception as e:
        error_json = get_error_msg('hio_get_rules_and_devs', e)
        return JsonResponse(error_json, status = 500)


def hio_update_monitored_devs(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    try:
        token = kwargs['token']
        loc = m.Location.objects.get(token=token)
    except Exception as e:
        return JsonResponse({"msg": repr(e)}, status = 400)

    try:
        # for each monitored device, update the status
        for entry in kwargs['update']:
            dev, cap, param = homeio_info_to_dev_cap_param(entry['dev_typ'], entry['dev_datatype'], entry['dev_address'])
            value, value_type = homeio_val_to_val(entry['val'], dev, param)
            dev_monitor = m.DeviceMonitor.objects.get(dev=dev, loc=loc)
            dev_monitor.value = value
            dev_monitor.value_type = value_type
            dev_monitor.save()
    except Exception as e:
        error_json = get_error_msg('hio_update_monitored_devs', e)
        return JsonResponse(error_json, status = 500)

    return JsonResponse({}, status=200)


def hio_upload_trace(request):
    try:
        kwargs = json.loads(request.body.decode('utf-8'))
        token = kwargs['token']
        loc = m.Location.objects.get(token=token)
    except Exception as e:
        error_json = get_error_msg('hio_upload_trace', e, status=400)
        return JsonResponse(error_json, status = 400)
    
    # err_json, status = check_access_to_location(request, loc.id)
    # if is_error(status):
    #     return JsonResponse(err_json, status=status)
    
    datatype_map = {
        'Bit': 'b',
        'Float': 'f',
        'DateTime': 'dt'
    }

    typ_map = {
        'Output': 'o',
        'Input': 'i',
        'Memory': 'm'
    }

    # load all traces into StateLog
    try:
        cache_token = kwargs['cache_token']
        if not cache_token:
            # this is the initial upload request
            # we need to initialize cache
            while True:
                cache_token = get_random_string(length=128)
                if cache.get(cache_token) is None:
                    break
            info_dict = {'log_list': []}
            cache.add(cache_token, info_dict)
            
        info_dict = cache.get(cache_token)
        log_list = info_dict['log_list']
        for entry in kwargs['trace']:
            if m.Device.objects.filter(typ=typ_map[entry['dev_typ']], 
                                       data_typ=datatype_map[entry['dev_datatype']], 
                                       address=entry['dev_address']).exists():
                sl_timestamp = datetime.datetime.strptime(
                    entry['timestamp'], '%H:%M:%S %m/%d/%Y')
                sl_timestamp = sl_timestamp.replace(tzinfo=pytz.utc)  # a placeholder timezone
                sl_status = m.StateLog.HAPPENED
                sl_dev, sl_cap, sl_param = homeio_info_to_dev_cap_param(entry['dev_typ'], entry['dev_datatype'], entry['dev_address'])
                sl_loc = loc
                sl_value, sl_value_type = homeio_val_to_val(entry['val'], sl_dev, sl_param)
                state_log = m.StateLog.objects.create(timestamp=sl_timestamp, 
                                                      status=sl_status, 
                                                      dev=sl_dev, 
                                                      cap=sl_cap,
                                                      param=sl_param,
                                                      loc=sl_loc,
                                                      value=sl_value,
                                                      value_type=sl_value_type,
                                                      is_superifttt=entry['is_automated'])
                log_entry = generate_dict_from_state_log(state_log, cluster=True)
                log_list.append(log_entry)
        

        info_dict['log_list'] = log_list
        cache.set(cache_token, info_dict)

        if kwargs['last']:
            initialize_trace_from_log_list(loc, log_list)
            cache.delete(cache_token)
            # initialize_trace_for_location(loc, True)
            loc.pending_trace = False
            loc.save()

    except Exception as e:
        error_json = get_error_msg('hio_upload_trace', e)
        return JsonResponse(error_json, status = 500)
    
    return JsonResponse({'cache_token': cache_token}, status=200)

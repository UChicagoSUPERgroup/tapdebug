from re import template
from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.core.cache import cache, caches
from django.utils.crypto import get_random_string
import backend.models as m
from autotapmc.analyze.Fix import generateCompactFix, generateNamedFix
from autotapmc.model.Tap import Tap
from autotapta.analyze.Analyze import extractEpisodes, listTimingCandidates, listRelatedCandidates, \
    listRelatedRevCandidates, synthesizeRuleGeneral, extractTriggerCases, debugRuleGeneral, filterFlipping, \
    extractRevertCases, fixByChangingCondition, extractTriggeringEvent, fixByAddingOrDeletingRule, \
    listRelatedRevCandidates, extractUnactuatedCases, extractTriggerCasesAlt, generateOppositeAction
from autotapta.model.Trace import enhanceTraceWithTiming, getSubTraceBasedOnCaps, enhanceTraceWithClock
from autotapta.analyze.Rank import calcScoreEnhanced, \
    checkIfEpisodeCovered, extractOrigNewTriggerTimes, calcScoreDebug, \
    calcScoreTapDebug, getTapListTriggerTime
from autotapta.analyze.Cluster import clusterBitVec
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from autotap.translator import tap_to_frontend_view, translate_sp_to_autotap_ltl, \
    translate_rule_into_autotap_tap, generate_all_device_templates, backend_to_frontend_view, \
    generate_boolean_map, autotapta_formula_to_clause, check_action_external, pv_clause_to_autotap_statement, \
    tap_to_frontend_view_ta, split_autotap_formula, dev_name_to_autotap, cap_name_to_autotap, var_name_to_autotap, \
    translate_clause_into_autotap_tap, patch_to_frontend_view, generate_cap_time_list_from_tap
from autotap.util import get_trace_for_location, get_sensor_dev_cap, get_action_dev_cap, \
    get_sensor_dev_cap_django, get_action_dev_cap_django, merge_times, find_time_clips, \
    translate_time_clip, generate_clip, translate_time_clip_debug, modify_patch_to_taps, delete_patch_to_taps, \
    translate_time_clip_feedback, translate_time_clip_helper, get_all_caps_in_taps, get_time_information_from_taps, \
    apply_tap_patch, tap_patch_complexity, getTraceMeta
from autotap.variable import generate_reverse_template, generate_autotap_name_for_dev_cap_param, \
    generate_cap_sensor_same_zone
from backend.util import record_request, record_response, get_dev_commands, get_param_vals, \
    check_access_to_location, is_error

import itertools
import json
import datetime
from numpy import array
from pytz import timezone
from copy import deepcopy
from timezonefinder import TimezoneFinder
from pytz import utc

# trace visualization
from autotap.parse_trace import parse_trace, parse_trace_new

def get_or_make_user(code,mode):
    try:
        user = m.User.objects.get(code=code, mode=mode)
    except m.User.DoesNotExist:
        user = m.User(code=code, mode=mode)
        user.save()

    return user


def get_user_id(user_id):
    n_code = False
    n_id = False
    try:
        user_id = m.User.objects.get(code=user_id).id
        return user_id
    except m.User.DoesNotExist:
        n_code = True
    try:
        user_id = m.User.objects.get(id=user_id).id
        return user_id
    except (m.User.DoesNotExist, ValueError):
        n_id = True

    if n_code and n_id:
        raise Exception("User %s does not exist." % str(user_id))


def expand_autotap_result_into_patches_named(patch_list, label_list, is_compact=False):
    if not is_compact:
        action_list = [tap.action for tap in patch_list]
        result_list = list()
        for selected_action in itertools.product(*action_list):
            patch = {k: tap_to_frontend_view(Tap(action=[s_a], condition=tap.condition, trigger=tap.trigger))
                     for k, s_a, tap in zip(label_list, selected_action, patch_list)}
            result_list.append(patch)
    else:
        result_list = {k: tap_to_frontend_view(tap) for k, tap in zip(label_list, patch_list)}
    return result_list


def expand_autotap_result_into_patches_unnamed(patch_list, is_compact=False):
    if not is_compact:
        action_list = [tap.action for tap in patch_list]
        result_list = list()
        for selected_action in itertools.product(*action_list):
            patch = [tap_to_frontend_view(Tap(action=[s_a], condition=tap.condition, trigger=tap.trigger))
                     for s_a, tap in zip(selected_action, patch_list)]
            result_list.append(patch)
    else:
        result_list = [tap_to_frontend_view(tap) for tap in patch_list]

    return result_list


def parse_fix_request(request):
    if request.method == 'GET':
        kwargs = request.GET
    elif request.method == 'POST':
        kwargs = json.loads(request.body.decode('utf-8'))
    else:
        raise Exception('The request is neither a POST or a GET.')

    try:
        user_rules = m.User.objects.get(id=kwargs['userid'], mode="rules")
        user_id_rules = user_rules.id
    except KeyError:
        user_id_rules = get_or_make_user(kwargs['code'], 'rules')

    try:
        user_sp = m.User.objects.get(id=kwargs['userid'], mode="sp")
        user_id_sp = user_sp.id
    except KeyError:
        user_id_sp = get_or_make_user(kwargs['code'], 'sp')

    task_id = kwargs['taskid']
    try:
        is_compact = int(kwargs['compact'])
    except KeyError:
        is_compact = 0

    try:
        is_named = int(kwargs['named'])
    except KeyError:
        is_named = 1

    return {'user_id_rules': user_id_rules, 'user_id_sp': user_id_sp,
            'task_id': task_id, 'is_compact': is_compact, 'is_named': is_named}


@csrf_exempt
def fix(request):
    json_resp = dict()
    try:
        req_dict = parse_fix_request(request)
        user_id_rules = req_dict['user_id_rules']
        user_id_sp = req_dict['user_id_sp']
        task_id = req_dict['task_id']
        is_named = req_dict['is_named']
        is_compact = req_dict['is_compact']

        rule_list = m.Rule.objects.filter(task=task_id, owner=user_id_rules)
        sp_list = m.SafetyProp.objects.filter(task=task_id, owner=user_id_sp)

        ltl_list = [translate_sp_to_autotap_ltl(sp) for sp in sp_list]
        if ltl_list:
            ltl = '!(%s)' % ' & '.join(ltl_list)
        else:
            ltl = '!(1)'

        template_dict = generate_all_device_templates()
        if is_named:
            tap_dict = {str(k): translate_rule_into_autotap_tap(v) for k, v in zip(range(len(rule_list)), rule_list)}
            tap_patch, tap_label = generateNamedFix(ltl, tap_dict, {}, template_dict)
            result_list = expand_autotap_result_into_patches_named(tap_patch, tap_label, is_compact)
            orig_rule_dict = {str(k): backend_to_frontend_view(v) for k, v in zip(range(len(rule_list)), rule_list)}

            json_resp['original'] = orig_rule_dict
            json_resp['patches'] = result_list
        else:
            tap_list = [translate_rule_into_autotap_tap(v) for v in rule_list]
            tap_patch = generateCompactFix(ltl, tap_list, {}, template_dict)
            result_list = expand_autotap_result_into_patches_unnamed(tap_patch, is_compact)
            orig_rule_list = [backend_to_frontend_view(v) for v in rule_list]

            json_resp['original'] = orig_rule_list
            json_resp['patches'] = result_list
        json_resp['succeed'] = True

    except Exception as exc:
        json_resp['patches'] = []
        json_resp['succeed'] = False
        json_resp['fail_exc'] = str(exc)
    return JsonResponse(json_resp)


def cluster_rules(mask_score_tap_list, location):
    if not mask_score_tap_list:
        return [], []  # no cluster if tap list is empty
    # Cluster the rules based on their mask
    mask_list = [mask for mask, _, _, _, _, _ in mask_score_tap_list]
    mask_list = array(mask_list)
    n_cluster, label_list = clusterBitVec(mask_list)

    mask_score_tap_cluster = [[] for _ in range(n_cluster)]
    orig_cluster = [[] for _ in range(n_cluster)]
    for m_s_t_t_f_r, label in zip(mask_score_tap_list, label_list):
        mask, score, tap, TP, FP, R = m_s_t_t_f_r
        f_clause = tap_to_frontend_view_ta(tap, location)
        mask_score_tap_cluster[label].append({'mask': mask, 'score': score, 
                                              'rule': f_clause, 'TP': TP, 'FP': FP, 'R': R})
        orig_cluster[label].append((score, tap))
    
    for cluster, index in zip(mask_score_tap_cluster, range(len(mask_score_tap_cluster))):
        cluster = sorted(cluster, key=lambda x: x['score'], reverse=True)
        mask_score_tap_cluster[index] = cluster
    
    for o_c, index in zip(orig_cluster, range(len(orig_cluster))):
        o_c = sorted(o_c, key=lambda x: x[0], reverse=True)
        orig_cluster[index] = o_c

    mask_score_tap_cluster = sorted(mask_score_tap_cluster, key=lambda x: x[0]['score'], reverse=True)
    orig_cluster = sorted(orig_cluster, key=lambda x: x[0][0], reverse=True)
    return mask_score_tap_cluster, orig_cluster


def cluster_patches(patches, patch_masks):
    # Cluster patches based on their types
    # Currently we only have one patch within one cluster
    # TODO: for new rules, should we cluster them?
    # patch_dict = {}
    res = []
    for patch, mask in zip(patches, patch_masks):
        if patch['mode'] in ('add-condition', 'delete-condition', 'modify-condition', 'modify-trigger'):
            # patch_key = ('modify-rule', patch['rule_id'])
            res.append({'mode': 'modify-rule', 'patches': [{'mask': mask, 'patch': patch}]})
        elif patch['mode'] in ('add-rule'):
            # patch_key = ('add-rule', -1)
            res.append({'mode': 'add-rule', 'patches': [{'mask': mask, 'patch': patch}]})
        elif patch['mode'] in ('delete-rule'):
            # patch_key = ('delete-rule', patch['rule_id'])
            res.append({'mode': 'delete-rule', 'patches': [{'mask': mask, 'patch': patch}]})
        else:
            raise Exception('Unknown patch type ' + patch['mode'])

        # if patch_key not in patch_dict:
        #     patch_dict[patch_key] = []
        # patch_dict[patch_key].append({'mask': mask, 'patch': patch})
    
    # return [{'mode': key, 'patches': patch_dict[key]} for key in patch_dict]
    return res


def suggest_rules_first_time(dev_c, command_c, location, second_time=False):
    target_dev = m.Device.objects.get(id=dev_c['id'])

    # Get current rules
    rule_set = m.Rule.objects.filter(location=location).order_by('id')
    orig_tap_list = [translate_rule_into_autotap_tap(rule, False) for rule in rule_set]

    # Translate trace, gather important information
    # print('stamp 1')
    trace = get_trace_for_location(location)
    # print('stamp 2')
    template_dict = generate_all_device_templates()

    # trace = reAssignRangeVariableInTrace(trace, template_dict=template_dict)
    # print('stamp 3')
    
    target_action = pv_clause_to_autotap_statement(dev_c, command_c['capability'], 
                                                command_c['parameter'], command_c['value'])
    orig_tap_list = [tap for tap in orig_tap_list if tap.action == target_action]

    # Select related variables
    cap_trigger = listTimingCandidates(trace, target_action, 6, template_dict=template_dict)
    cap_trigger = cap_trigger[:3] if not second_time else cap_trigger[3:]
    cap_condition = listRelatedCandidates(trace, target_action, 3, template_dict=template_dict)

    cap_time_list = [(cap, time) for cap, time, _ in cap_trigger if time > 1]
    cap_trigger_list = [cap for cap, _, _ in cap_trigger]
    cap_condition_list = [cap for cap, _ in cap_condition]

    cap_list = [cap for cap, _, _ in cap_trigger]
    cap_list = cap_list + [cap for cap, _ in cap_condition]
    cap_list = list(set(cap_list))
    target_cap = target_action.split('=')[0]
    if target_cap not in cap_list:
        cap_list.append(target_cap)

    # print('stamp 4')
    # All sensors that can influence the target action in taps should be added
    orig_tap_time_list = []
    for tap in orig_tap_list:
        if tap.action.startswith(target_cap):
            dev, cap, par, _, _ = split_autotap_formula(tap.trigger)
            orig_tap_time_list += generate_cap_time_list_from_tap(tap)
            cap = dev + '.' + cap + '_' + par
            # if time is not None and (cap, time) not in cap_time_list:
            #     cap_time_list.append((cap, time))
            if cap not in cap_list:
                cap_list.append(cap)
            # if cap not in cap_trigger_list:
            #     cap_trigger_list.append(cap)
            for cond in tap.condition:
                dev, cap, par, _, _ = split_autotap_formula(cond)
                cap = dev + '.' + cap + '_' + par
                if cap not in cap_list:
                    cap_list.append(cap)

    # Get traces only relating to selected variables
    # Should go from trace instead of log_list
    trace = getSubTraceBasedOnCaps(trace, cap_list)
    # filter out the revert actions
    trace = filterFlipping(trace, target_action)
    # enhance with timing
    new_trace = enhanceTraceWithTiming(trace, list(set(cap_time_list+orig_tap_time_list)), '*')

    # print('stamp 5')
    # Gather episodes, and learn
    # TODO: should take away the actions that is triggered by the system
    raw_episode_list = extractEpisodes(new_trace, target_action, 
                                       pre_time_span=datetime.timedelta(seconds=settings.PRE_TIME), 
                                       post_time_span=datetime.timedelta(seconds=settings.POST_TIME))
    episode_list = []
    # take away episodes that are already handled by the current taps

    for episode in raw_episode_list:
        # for tap in orig_tap_list:
        #     if getTriggerTimeInTrace(episode, tap, check_enable=False):
        #         # this trace is handled by existing rules
        #         break
        # else:
        #     # this trace is not handled yet
        #     episode_list.append(episode)
        if not checkIfEpisodeCovered(episode, orig_tap_list, target_action):
            episode_list.append(episode)

    # print('stamp 6')
    mask_tap_list = synthesizeRuleGeneral(episode_list, target_action, learning_rate=settings.LEARNING_RATE_SYN,
                                            variable_list=cap_list, trig_var_list=cap_trigger_list,
                                            cond_var_list=cap_condition_list,
                                            timing_cap_list=cap_time_list,
                                            template_dict=template_dict, tap_list=orig_tap_list)
    if not mask_tap_list and not second_time:
        return suggest_rules_first_time(dev_c, command_c, location, second_time=True)
    # print('stamp 7')

    # Calculate the score of rules (for ranking)
    mask_score_tap_list = []
    for mask, tap in mask_tap_list:
        score, TP, FP, R = calcScoreEnhanced(new_trace, target_action, tap, 
                                             pre_time_span=settings.PRE_TIME, 
                                             post_time_span=settings.POST_TIME)
        mask_score_tap_list.append((mask, score, tap, TP, FP, R))

    # print('stamp 8')
    # Cluster the rules based on their mask
    mask_score_tap_cluster, orig_tap_cluster = cluster_rules(mask_score_tap_list, location)
    json_resp = {'rules': mask_score_tap_cluster}
    json_resp['orig_rules'] = [backend_to_frontend_view(rule) for rule in rule_set 
                               if translate_rule_into_autotap_tap(rule).action == target_action]

    # print('stamp 9')
    # Update cache
    while True:
        cache_token = get_random_string(length=128)
        if cache.get(cache_token) is None:
            break
    cache_entry = {
        'episode_list': episode_list, 
        'orig_trace': trace, 
        'trace': new_trace, 
        'target_action': target_action, 
        'cap_list': cap_list, 
        'cap_trigger_list': cap_trigger_list,
        'cap_condition_list': cap_condition_list,
        'cap_time_list': cap_time_list,
        'template_dict': template_dict,
        'location': location,
        'orig_tap_list': orig_tap_list,
        'orig_rules_frontend': json_resp['orig_rules'],
        'current_rules': orig_tap_cluster,
        'mask_score_tap_cluster': mask_score_tap_cluster
    }
    cache.add(cache_token, cache_entry)
    json_resp['token'] = cache_token
    json_resp['n_episodes'] = len(episode_list)

    # print('stamp 10')

    return json_resp


def suggest_rules_follow_up(mask, token):
    json_resp = dict()
    cache_entry = cache.get(token)
    if cache_entry is None:
        json_resp['cache_found'] = False
        return json_resp
    else:
        json_resp['cache_found'] = True
    episode_list = cache_entry['episode_list']
    new_trace = cache_entry['trace']
    target_action = cache_entry['target_action']
    cap_list = cache_entry['cap_list']
    cap_trigger_list = cache_entry['cap_trigger_list']
    cap_condition_list = cache_entry['cap_condition_list']
    cap_time_list = cache_entry['cap_time_list']
    template_dict = cache_entry['template_dict']
    location = cache_entry['location']
    orig_tap_list = cache_entry['orig_tap_list']
    orig_rules_frontend = cache_entry['orig_rules_frontend']

    mask_tap_list = synthesizeRuleGeneral(episode_list, target_action, learning_rate=0.5,
                                          variable_list=cap_list, trig_var_list=cap_trigger_list,
                                          cond_var_list=cap_condition_list,
                                          timing_cap_list=cap_time_list,
                                          template_dict=template_dict, mask=mask, tap_list=orig_tap_list)

    # Calculate the score of rules (for ranking)
    mask_score_tap_list = []
    for rule_mask, tap in mask_tap_list:
        score, TP, FP, R = calcScoreEnhanced(new_trace, target_action, tap, 
                                             pre_time_span=settings.PRE_TIME, 
                                             post_time_span=settings.POST_TIME)
        mask_score_tap_list.append((rule_mask, score, tap, TP, FP, R))

    # Cluster the rules based on their mask
    mask_score_tap_cluster, orig_tap_cluster = cluster_rules(mask_score_tap_list, location)
    json_resp['rules'] = mask_score_tap_cluster
    json_resp['orig_rules'] = orig_rules_frontend

    cache_entry['current_rules'] = orig_tap_cluster
    cache_entry['mask_score_tap_cluster'] = mask_score_tap_cluster
    cache.set(token, cache_entry)

    return json_resp


def suggestadd(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    loc_id = kwargs['locid']
    err_json, status = check_access_to_location(request, loc_id)
    if is_error(status):
        return JsonResponse(err_json, status=status)

    location = m.Location.objects.get(id=loc_id)

    try:
        if kwargs['first_time']:
            record_request(kwargs, 'syn_first', location)
            dev_c = kwargs['device']
            command_c = kwargs['command']
            json_resp = suggest_rules_first_time(dev_c, command_c, location)
            record_response(json_resp, 'syn_first', location)
        else:
            record_request(kwargs, 'syn_followup', location)
            mask = kwargs['mask']
            token = kwargs['token']
            json_resp = suggest_rules_follow_up(mask, token)
            record_response(json_resp, 'syn_followup', location)

        return JsonResponse(json_resp)
        
    except Exception as e:
        return JsonResponse({"msg": repr(e)}, status=500)



def suggest_debug_first_time(dev_c, command_c):
    target_dev = m.Device.objects.get(id=dev_c['id'])
    location = target_dev.location

    # Get current rules
    rule_set = list(m.Rule.objects.filter(st_installed_app_id=location.st_installed_app_id).order_by('id'))
    orig_tap_list = [translate_rule_into_autotap_tap(rule, use_tick_header=False) for rule in rule_set]

    # Translate trace, gather important information
    trace = get_trace_for_location(location)
    template_dict = generate_all_device_templates()
    
    target_action = pv_clause_to_autotap_statement(dev_c, command_c['capability'], 
                                                command_c['parameter'], command_c['value'])

    target_dev_cap = (dev_c['label'] if dev_c['label'] else dev_c['name'], command_c['capability']['name'])
    
    orig_tap_id_list = [rule.id for tap, rule in zip(orig_tap_list, rule_set) if tap.action == target_action]
    orig_rule_dev_cap_list = [get_sensor_dev_cap_django(rule) 
                              for tap, rule in zip(orig_tap_list, rule_set) 
                              if tap.action == target_action]
    orig_tap_list = [tap for tap in orig_tap_list if tap.action == target_action]

    # Select related variables (all in the debugging case)
    cap_list = trace.system.getFieldNameList()
    cap_condition_list = []
    for cap in cap_list:
        dev, par = cap.split('.')
        if 'external' in template_dict[dev][par]:
            cap_condition_list.append(cap)

    # Get all timing information in the triggers
    cap_time_list = []
    target_cap = target_action.split('=')[0]
    for tap in orig_tap_list:
        if tap.action.startswith(target_cap):
            dev, cap, par, _, _ = split_autotap_formula(tap.trigger)
            tap_trigger = tap.trigger[5:-1] if tap.trigger.startswith('tick') else tap.trigger
            if '#' in tap_trigger:
                time = int(tap_trigger.split('#')[0])
            elif '*' in tap_trigger:
                time = int(tap_trigger.split('*')[0])
            else:
                time = None
            if time is not None:
                cap_time_list.append((dev + '.' + cap + '_' + par, time))

    # Get traces only relating to selected variables, enhance with timing
    # Should go from trace instead of log_list
    trace = getSubTraceBasedOnCaps(trace, cap_list)
    new_trace = enhanceTraceWithTiming(trace, cap_time_list, '*')

    # Gather episodes, and learn
    time_event_cond_list, revert_list = extractTriggerCases(
        new_trace, target_action, tap_list=orig_tap_list, pre_time_span=datetime.timedelta(seconds=settings.MAX_AUTOMATION_TIME))

    delete_dev_cap_list = []
    modify_dev_cap_list = []

    if sum(revert_list):
        delete_patches, modify_patches, delete_rule_masks, modify_rule_masks = \
            debugRuleGeneral(new_trace, time_event_cond_list, revert_list, target_action, learning_rate=0.5,
                             variable_list=cap_list, cond_var_list=cap_condition_list,
                             template_dict=template_dict, tap_list=orig_tap_list)

        modify_patch_meta_list = []
        delete_patch_meta_list = []
        modify_rule_masks = []
        delete_rule_masks = []

        for m_p in modify_patches:
            new_tap_list = modify_patch_to_taps(orig_tap_list, m_p)
            score, TP, FP, mask = calcScoreDebug(new_trace.system, time_event_cond_list, revert_list, new_tap_list)
            modify_patch_meta_list.append((score, TP, FP))
            modify_rule_masks.append(mask)
        for d_p in delete_patches:
            new_tap_list = delete_patch_to_taps(orig_tap_list, d_p)
            score, TP, FP, mask = calcScoreDebug(new_trace.system, time_event_cond_list, revert_list, new_tap_list)
            delete_patch_meta_list.append((score, TP, FP))
            delete_rule_masks.append(mask)
        
        delete = [{'id': orig_tap_id_list[d['index']], 'score': meta[0], 'TP': meta[1], 'FP': meta[2]} 
                  for d, meta in zip(delete_patches, delete_patch_meta_list)]
        delete_dev_cap_list = [orig_rule_dev_cap_list[d['index']] for d in delete_patches]
        modify = []
        for d, meta in zip(modify_patches, modify_patch_meta_list):
            rule_id = orig_tap_id_list[d['index']]
            tap = deepcopy(orig_tap_list[d['index']])
            tap.condition.append(d['new_condition'])
            frontend_tap = tap_to_frontend_view_ta(tap, location)
            frontend_tap['id'] = rule_id
            modify_dev_cap_list.append(get_sensor_dev_cap(frontend_tap))
            modify.append({'id': rule_id, 'rule': frontend_tap, 'score': meta[0], 'TP': meta[1], 'FP': meta[2]})
        
        patches = [{**m, 'typ': 'modify'} for m in modify] + [{**d, 'typ': 'delete'} for d in delete]
        rule_masks = modify_rule_masks + delete_rule_masks
        rule_dev_cap_list = modify_dev_cap_list + delete_dev_cap_list
        comb = [(p, m, dc) for p, m, dc in zip(patches, rule_masks, rule_dev_cap_list)]
        comb = sorted(comb, key=lambda x:x[0]['score'], reverse=True)
        patches = [p for p, _, _ in comb]
        rule_masks = [m for _, m, _ in comb]
        rule_dev_cap_list = [dc for _, _, dc in comb]

    else:
        patches = []
        rule_masks = []

    # Update cache
    while True:
        cache_token = get_random_string(length=128)
        if cache.get(cache_token) is None:
            break
    cache_entry = {
        'trace': new_trace, 
        'target_action': target_action, 
        'cap_list': cap_list, 
        'cap_condition_list': cap_condition_list,
        'template_dict': template_dict,
        'location': location,
        'time_event_cond_list': time_event_cond_list,
        'rule_masks': rule_masks,
        'orig_tap_list': orig_tap_list,
        'rule_dev_cap_list': rule_dev_cap_list,
        'target_dev_cap': target_dev_cap,
        'revert_list': revert_list
    }
    cache.add(cache_token, cache_entry)

    json_resp = dict()
    json_resp['patches'] = patches
    json_resp['rule_masks'] = rule_masks
    json_resp['token'] = cache_token
    json_resp['orig_rules'] = [backend_to_frontend_view(rule) for rule in rule_set 
                               if translate_rule_into_autotap_tap(rule).action == target_action]
    return json_resp


def suggest_debug_follow_up(rules, token):
    json_resp = dict()
    cache_entry = cache.get(token)
    if cache_entry is None:
        json_resp['cache_found'] = False
        return json_resp
    else:
        json_resp['cache_found'] = True
    new_trace = cache_entry['trace']
    target_action = cache_entry['target_action']
    cap_list = cache_entry['cap_list']
    cap_condition_list = cache_entry['cap_condition_list']
    template_dict = cache_entry['template_dict']
    orig_tap_list = [translate_clause_into_autotap_tap(rule, False) for rule in rules]
    orig_rule_dev_cap_list = [get_sensor_dev_cap(rule) for rule in rules]
    orig_tap_id_list = [rule['id'] for rule in rules]
    location = cache_entry['location']
    
    # Gather episodes, and learn
    time_event_cond_list, revert_list = extractTriggerCases(
        new_trace, target_action, tap_list=orig_tap_list, pre_time_span=datetime.timedelta(seconds=settings.MAX_AUTOMATION_TIME))

    delete_dev_cap_list = []
    modify_dev_cap_list = []

    if sum(revert_list):
        delete_patches, modify_patches, delete_rule_masks, modify_rule_masks = \
            debugRuleGeneral(new_trace, time_event_cond_list, revert_list, target_action, learning_rate=0.5,
                             variable_list=cap_list, cond_var_list=cap_condition_list,
                             template_dict=template_dict, tap_list=orig_tap_list)
        
        modify_patch_meta_list = []
        delete_patch_meta_list = []
        modify_rule_masks = []
        delete_rule_masks = []
        for m_p in modify_patches:
            new_tap_list = modify_patch_to_taps(orig_tap_list, m_p)
            score, TP, FP, mask = calcScoreDebug(new_trace.system, time_event_cond_list, revert_list, new_tap_list)
            modify_patch_meta_list.append((score, TP, FP))
            modify_rule_masks.append(mask)
        for d_p in delete_patches:
            new_tap_list = delete_patch_to_taps(orig_tap_list, d_p)
            score, TP, FP, mask = calcScoreDebug(new_trace.system, time_event_cond_list, revert_list, new_tap_list)
            delete_patch_meta_list.append((score, TP, FP))
            delete_rule_masks.append(mask)

        delete = [{'id': orig_tap_id_list[d['index']], 'score': meta[0], 'TP': meta[1], 'FP': meta[2]} 
                  for d, meta in zip(delete_patches, delete_patch_meta_list)]
        delete_dev_cap_list = [orig_rule_dev_cap_list[d['index']] for d in delete_patches]
        modify = []
        for d, meta in zip(modify_patches, modify_patch_meta_list):
            rule_id = orig_tap_id_list[d['index']]
            tap = deepcopy(orig_tap_list[d['index']])
            tap.condition.append(d['new_condition'])
            frontend_tap = tap_to_frontend_view_ta(tap, location)
            frontend_tap['id'] = rule_id
            modify_dev_cap_list.append(get_sensor_dev_cap(frontend_tap))
            modify.append({'id': rule_id, 'rule': frontend_tap, 'score': meta[0], 'TP': meta[1], 'FP': meta[2]})

        patches = [{**m, 'typ': 'modify'} for m in modify] + [{**d, 'typ': 'delete'} for d in delete]
        rule_masks = modify_rule_masks + delete_rule_masks
        rule_dev_cap_list = modify_dev_cap_list + delete_dev_cap_list
        comb = [(p, m, dc) for p, m, dc in zip(patches, rule_masks, rule_dev_cap_list)]
        comb = sorted(comb, key=lambda x:x[0]['score'], reverse=True)
        patches = [p for p, _, _ in comb]
        rule_masks = [m for _, m, _ in comb]
        rule_dev_cap_list = [dc for _, _, dc in comb]
    else:
        patches = []
        rule_masks = []
    
    # update cache
    cache_entry['time_event_cond_list'] = time_event_cond_list
    cache_entry['rule_masks'] = rule_masks
    cache_entry['rule_dev_cap_list'] = rule_dev_cap_list
    cache.set(token, cache_entry)

    json_resp['patches'] = patches
    json_resp['rule_masks'] = rule_masks
    json_resp['token'] = token
    return json_resp


def suggestdebug(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    loc_id = kwargs['locid']
    err_json, status = check_access_to_location(request, loc_id)
    if is_error(status):
        return JsonResponse(err_json, status=status)

    location = m.Location.objects.get(id=loc_id)

    try:
        if kwargs['first_time']:
            record_request(kwargs, 'debug_first', location)
            dev_c = kwargs['device']
            command_c = kwargs['command']
            json_resp = suggest_debug_first_time(dev_c, command_c)
            record_response(json_resp, 'debug_first', location)
        else:
            record_request(kwargs, 'debug_followup', location)
            token = kwargs['token']
            rules = kwargs['rules']
            json_resp = suggest_debug_follow_up(rules, token)
            record_response(json_resp, 'debug_followup', location)

        return JsonResponse(json_resp)
        
    except Exception as e:
        return JsonResponse({"msg": repr(e)}, status=500)


def _get_autotap_cap_from_state_log(state_log):
    dev_name = state_log.dev.name if state_log.dev.dev_type == 'v' else state_log.dev.label
    cap_name = state_log.cap.name
    param_name = state_log.param.name
    autotap_dev_name = dev_name_to_autotap(dev_name)
    autotap_cap_name = cap_name_to_autotap(cap_name)
    autotap_param_name = var_name_to_autotap(param_name)
    return autotap_dev_name + '.' + autotap_cap_name + '_' + autotap_param_name


def getepisode(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    loc_id = kwargs['locid']
    err_json, status = check_access_to_location(request, loc_id)
    if is_error(status):
        return JsonResponse(err_json, status=status)

    # mask = kwargs['mask']
    token = kwargs['vis_token']
    cache_entry = cache.get(token)

    # gather information from the cache
    trace = cache_entry['trace']
    fn_episodes = cache_entry['fn_episode_list']
    time_event_cond_list = cache_entry['time_event_cond_list']
    revert_list = cache_entry['revert_list']
    cap_list = cache_entry['cap_list']
    cap_time_list = cache_entry['cap_time_list']
    orig_tap_list = cache_entry['orig_tap_list']
    target_action = cache_entry['target_action']
    patches = cache_entry['patches']
    patch_masks = cache_entry['patch_masks']
    existing_time_points = cache_entry['existing_time_points']

    # calculate meta info for each patch
    #   times when it's triggered
    #   times when it introduces new triggered actions (new introduced)
    #   mask for fn_episodes (whether the each fn is solved by the patch)
    #   mask for tec_episodes (time_event_cond) (whether each entry is a 1: FP_fixed, or 2: TP_cancelled for the patch)
    #   mask for ni_episodes (new_introduced) (whether each episode contains new actions introduced by the patch) <- calculated later
    patch_meta_list = []
    for patch, mask in zip(patches, patch_masks):
        new_tap_list = apply_tap_patch(orig_tap_list, patch)
        _, meta = calcScoreTapDebug(new_tap_list, trace, mask, revert_list, time_event_cond_list, fn_episodes, existing_time_points)
        # calc mask for fn_episodes
        mask_fn = mask[len(revert_list):]
        # calc mask for tec episodes
        lambda_tec_class = lambda preserved, reverted: 1 if not preserved and reverted else (2 if not preserved and not reverted else 0)
        mask_tec = [lambda_tec_class(preserved, reverted) for preserved, reverted in zip(mask[:len(revert_list)], revert_list)]

        # save information
        meta['tap_list'] = new_tap_list
        meta['mask_fn'] = mask_fn
        meta['mask_tec'] = mask_tec
        patch_meta_list.append(meta)
    
    # combine new_introduced times for each patch into time clips [(start, end)...]
    # generate episodes for new_introduced actions (ni_episodes)
    all_new_intro_times = []
    for meta in patch_meta_list:
        all_new_intro_times += meta['time_points_outside_fn']
    all_new_intro_times = sorted(list(set(all_new_intro_times)))
    new_introduced_time_clips = find_time_clips(all_new_intro_times, span=datetime.timedelta(seconds=settings.VIS_DEBUG))
    ni_episodes = [generate_clip(trace, start, end) for start, end in new_introduced_time_clips]

    # calculate mask_ni for each patch
    for meta in patch_meta_list:
        time_points_outside_fn = meta['time_points_outside_fn']
        mask_ni = []
        for start, end in new_introduced_time_clips:
            mask_ni.append(any(t >= start and t <= end for t in time_points_outside_fn))
        meta['mask_ni'] = mask_ni
    
    # generate episodes for time_event_cond (tec_episodes)
    tec_time_window = datetime.timedelta(seconds=settings.VIS_DEBUG)
    tec_episodes = [generate_clip(trace, time-tec_time_window, time+tec_time_window) for time, _, _ in time_event_cond_list]

    # translate time clips: should encode patch behavior into the generated vis
    # generate translated fn_episodes
    rev_map = generate_reverse_template()
    newly_triggered_events = []  # a list of (time, index) where index is the index of the patch
    for index in range(len(patch_meta_list)):
        meta = patch_meta_list[index]
        newly_triggered_times = meta['time_points_inside_fn']
        newly_triggered_events += [(time, index) for time in newly_triggered_times]
    newly_triggered_events = sorted(newly_triggered_events)

    fn_vis_list = []
    for episode_index in range(len(fn_episodes)):
        # for each episode in fn_episodes, do the translation
        episode = fn_episodes[episode_index]
        time_dict, shown_new_tap = translate_time_clip(episode, target_action, newly_triggered_events, 
                                                        n_new_tap=len(patch_meta_list), rev_map=rev_map)
        fn_vis_list.append(time_dict)
    
    # generate translated ni_episodes
    newly_triggered_events = []  # a list of (time, index) where index is the index of the patch
    for index in range(len(patch_meta_list)):
        meta = patch_meta_list[index]
        newly_triggered_times = meta['time_points_outside_fn']
        newly_triggered_events += [(time, index) for time in newly_triggered_times]
    newly_triggered_events = sorted(newly_triggered_events)

    ni_vis_list = []
    for episode_index in range(len(ni_episodes)):
        # for each episode in fn_episodes, do the translation
        episode = ni_episodes[episode_index]
        time_dict, shown_new_tap = translate_time_clip(episode, target_action, newly_triggered_events, 
                                                        n_new_tap=len(patch_meta_list), rev_map=rev_map)
        ni_vis_list.append(time_dict)

    # generate translated tec_episodes
    tec_vis_list = []
    for index in range(len(time_event_cond_list)):
        time, event, pre_cond = time_event_cond_list[index]
        episode = tec_episodes[index]
        event_id = episode.actions.index((time, event))  # the event triggering original rules (potentially cancelled)
        action_id = -1
        # it could be a prevented action that did not appear in the trace
        for ii in range(event_id+1, len(episode.actions)):
            if not episode.is_ext_list[ii] and episode.actions[ii][1] == target_action:
                action_id = ii
                break
        debug_unactuated_tup = None
        if action_id == -1:
            # this means that the original action is unactuated, but fixed
            debug_unactuated_tup = (time, target_action, pre_cond)
        
        time_dict = translate_time_clip_debug(episode, action_id, rev_map, debug_unactuated_tup=debug_unactuated_tup)
        tec_vis_list.append(time_dict)

    # mark sensor id shown up in rules, mark target action id
    dev_list = [rev_map[cap][0].name for cap in trace.system.getFieldNameList()]
    cap_list = [rev_map[cap][1].name for cap in trace.system.getFieldNameList()]
    dev_cap_list = [(dev, cap) for dev, cap in zip(dev_list, cap_list)]
    rule_sensor_list = []
    for meta in patch_meta_list:
        tap_list = meta['tap_list']
        dc_list_for_patch = []
        for tap in tap_list:
            frontend_tap = tap_to_frontend_view_ta(tap, None)
            d_c_list = get_sensor_dev_cap(frontend_tap)
            dc_list_for_patch += d_c_list
        dc_list_for_patch = set(dc_list_for_patch)
        rule_sensor_list.append([dev_cap_list.index(d_c) for d_c in dc_list_for_patch])
    target_id = trace.system.getFieldNameList().index(target_action.split('=')[0])
    
    json_resp = {
        'fn_vis_list': parse_trace_new(fn_vis_list), 
        'tec_vis_list': parse_trace_new(tec_vis_list),
        'ni_vis_list': parse_trace_new(ni_vis_list),
        'masks_fn': [meta['mask_fn'] for meta in patch_meta_list],
        'masks_tec': [meta['mask_tec'] for meta in patch_meta_list],
        'masks_ni': [meta['mask_ni'] for meta in patch_meta_list],
        'dev_list': dev_list, 
        'cap_list': cap_list, 'rule_sensor_list': rule_sensor_list,
        'target_id': target_id,
        'n_revert': sum(revert_list)
    } # parse log as HTML
    return JsonResponse(json_resp)


def getepisode_debug(request):
    if request.user.is_authenticated:
        kwargs = json.loads(request.body.decode('utf-8'))
        token = kwargs['token']
        cache_entry = cache.get(token)

        time_event_cond_list = cache_entry['time_event_cond_list']
        revert_list = cache_entry['revert_list']
        rule_masks = cache_entry['rule_masks']
        rule_dev_cap_list = cache_entry['rule_dev_cap_list']
        location = cache_entry['location']
        target_action = cache_entry['target_action']
        trace = cache_entry['trace']  # should be enhanced with timing
        rev_map = generate_reverse_template(loc=location)

        dev_cap_list = []
        trace_vis_list = []

        time_window = datetime.timedelta(seconds=settings.VIS_DEBUG)
        time_dict_list = []
        for time, event, _ in time_event_cond_list:
            episode = generate_clip(trace, time-time_window, time+time_window)
            event_id = episode.actions.index((time, event))
            action_id = -1
            for ii in range(event_id+1, len(episode.actions)):
                if not episode.is_ext_list[ii] and episode.actions[ii][1] == target_action:
                    action_id = ii
                    break
            time_dict = translate_time_clip_debug(episode, action_id, rev_map)
            time_dict_list.append(time_dict)

        trace_vis_list = parse_trace_new(time_dict_list)

        device_list = [rev_map[cap][0].name for cap in trace.system.getFieldNameList()]
        capability_list = [rev_map[cap][1].name for cap in trace.system.getFieldNameList()]
        dev_cap_list = [(dev, cap) for dev, cap in zip(device_list, capability_list)]
        target_dev_cap_id = trace.system.getFieldNameList().index(target_action.split('=')[0])

        rule_sensor_list = []
        for d_c_l in rule_dev_cap_list:
            sensor_list = []
            for dev, cap in d_c_l:
                index = dev_cap_list.index((dev, cap))
                if index != target_dev_cap_id:
                    sensor_list.append(index)
            rule_sensor_list.append(sensor_list)

        trace_vis_list_positive = []
        trace_vis_list_negative = []
        rule_mask_positive = [[] for _ in rule_masks]
        rule_mask_negative = [[] for _ in rule_masks]
        for index in range(len(trace_vis_list)):
            trace_vis = trace_vis_list[index]
            reverted = revert_list[index]
            if reverted:  # should be handled
                trace_vis_list_positive.append(trace_vis)
                for rule_id in range(len(rule_masks)):
                    rule_mask_positive[rule_id].append(rule_masks[rule_id][index])
            else:
                trace_vis_list_negative.append(trace_vis)
                for rule_id in range(len(rule_masks)):
                    rule_mask_negative[rule_id].append(rule_masks[rule_id][index])

        json_resp = {'log_list_positive': trace_vis_list_positive, 'log_list_negative': trace_vis_list_negative, 
                     'dev_list': device_list, 'cap_list': capability_list, 
                     'rule_sensor_list': rule_sensor_list, 'target_id': target_dev_cap_id, 
                     'rule_mask_positive': rule_mask_positive, 'rule_mask_negative': rule_mask_negative} # parse log as HTML
        return JsonResponse(json_resp)
    else:
        return JsonResponse({"msg": "Please log in first!"}, status=401)


def getepisode_feedback(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    loc_id = kwargs['locid']
    err_json, status = check_access_to_location(request, loc_id)
    if is_error(status):
        return JsonResponse(err_json, status=status)
    
    location = m.Location.objects.get(id=loc_id)

    try:
        dev_c = kwargs['device']
        command_c = kwargs['command']
        target_dev = m.Device.objects.get(id=dev_c['id'])

        # first get trace
        trace = get_trace_for_location(location)
        target_zone = m.Device.objects.get(id=dev_c['id']).zone
        cap_rst = generate_cap_sensor_same_zone(target_zone)

        template_dict = generate_all_device_templates()
        target_action = pv_clause_to_autotap_statement(dev_c, command_c['capability'], 
                                                       command_c['parameter'], command_c['value'])

        # get current rules related to the target action
        rule_set = m.Rule.objects.filter(location=location).order_by('id')
        orig_rules = [backend_to_frontend_view(rule) for rule in rule_set 
                      if translate_rule_into_autotap_tap(rule).action == target_action]
        full_tap_list = [translate_rule_into_autotap_tap(rule) for rule in rule_set]
        orig_tap_list = [translate_rule_into_autotap_tap(rule) for rule in rule_set 
                         if translate_rule_into_autotap_tap(rule).action == target_action]
        
        # select related caps
        time_event_cond_list, revert_list = extractTriggerCases(
            trace, target_action, tap_list=orig_tap_list, pre_time_span=datetime.timedelta(seconds=settings.MAX_AUTOMATION_TIME))
        cap_trigger = listTimingCandidates(
            trace, target_action, 6, template_dict=template_dict, cap_rst=cap_rst)
        cap_trigger = cap_trigger[:3]
        cap_condition = listRelatedCandidates(trace, target_action, 3, template_dict=template_dict, cap_rst=cap_rst)
        cap_condition_rev = listRelatedRevCandidates(trace, time_event_cond_list, 
                                                 revert_list, target_action, 2, cap_rst=cap_rst, 
                                                 cap_skip={cap for cap, _ in cap_condition}, 
                                                 template_dict=template_dict)

        cap_list = [cap for cap, _, _ in cap_trigger]
        cap_list = cap_list + [cap for cap, _ in cap_condition] + [cap for cap, _ in cap_condition_rev]
        cap_list = list(set(cap_list))

        cap_time_list = [(cap, time) for cap, time, _ in cap_trigger if time > 1]
        cap_trigger_list = [cap for cap, _, _ in cap_trigger]
        cap_condition_list = [cap for cap, _ in cap_condition] + [cap for cap, _ in cap_condition_rev]

        target_cap = target_action.split('=')[0]
        if target_cap not in cap_list:
            cap_list.append(target_cap)
        

        # add all caps shown up to cap_list
        tap_cap_list = get_all_caps_in_taps(orig_tap_list)
        for cap in tap_cap_list:
            if cap not in cap_list:
                cap_list.append(cap)
        # add all caps shown up in cond to cap_condition_list
        tap_cond_cap_list = get_all_caps_in_taps(orig_tap_list, only_cond=True)
        for cap in tap_cond_cap_list:
            if cap not in cap_condition_list:
                cap_condition_list.append(cap)
        tap_cap_time_list, tap_clock_list = get_time_information_from_taps(orig_tap_list)

        # cut off unrelated caps from trace
        trace = getSubTraceBasedOnCaps(trace, cap_list)

        # we should enhance trace with the timing information from the rules
        trace = enhanceTraceWithTiming(trace, tap_cap_time_list, '*')
        trace = enhanceTraceWithClock(trace, tap_clock_list)

        # get episodes from trace (subtrace in which target action happened)
        episode_list = extractEpisodes(trace, target_action, 
                                       pre_time_span=datetime.timedelta(seconds=settings.PRE_TIME), 
                                       post_time_span=datetime.timedelta(seconds=settings.VIS_POST_TIME),
                                       consider_automated=True, consider_reverted=True, 
                                       consider_all_target_dev=True)

        # translate episodes into vis format
        # should also store a reference_dict so that feedback can 
        # refer to a specific automated action
        rev_map = generate_reverse_template(loc=location)
        target_id = trace.system.getFieldNameList().index(target_action.split('=')[0])
        clip_list = []
        reference_dict = {}
        episodes_unactuated_list = []
        for ii in range(len(episode_list)):
            episode = episode_list[ii]
            unactuated_list = extractUnactuatedCases(episode, target_action, orig_tap_list, 
                                   pre_time_span=datetime.timedelta(seconds=settings.MAX_AUTOMATION_TIME))
            episodes_unactuated_list.append(unactuated_list)
            unactuated_list = [(t, target_action, pre_c) for t, _, pre_c in unactuated_list]
            time_list, ref_dict_single = translate_time_clip_feedback(episode, rev_map, unactuated_list=unactuated_list)
            clip_list.append(time_list)
            for date_str, cap_id, entry_id in ref_dict_single:
                if cap_id == target_id:
                    reference_dict[(ii, date_str, entry_id)] = ref_dict_single[(date_str, cap_id, entry_id)]

        # clip_list = [translate_time_clip_debug(episode, -1, rev_map) for episode in episode_list]
        trace_logs = parse_trace_new(clip_list)

        # get dev list, cap list
        device_list = [rev_map[cap][0].name for cap in trace.system.getFieldNameList()]
        capability_list = [rev_map[cap][1].name for cap in trace.system.getFieldNameList()]

        # Update cache
        while True:
            cache_token = get_random_string(length=128)
            if cache.get(cache_token) is None:
                break
        cache_entry = {
            'episode_list': episode_list, 
            'clip_list': clip_list, 
            'trace_logs': trace_logs,
            'reference_dict': reference_dict,
            'cap_list': cap_list, 
            'target_action': target_action,
            'cap_trigger_list': cap_trigger_list,
            'cap_condition_list': cap_condition_list,
            'cap_time_list': cap_time_list,
            'template_dict': template_dict,
            'orig_tap_list': orig_tap_list,
            'full_tap_list': full_tap_list,
            'trace': trace,
            'orig_rules': orig_rules,
            'episodes_unactuated_list': episodes_unactuated_list
        }

        cache.add(cache_token, cache_entry)
        # response json
        json_resp = {
            'log_list': trace_logs, 'dev_list': device_list, 
            'cap_list': capability_list, 'orig_rules': orig_rules,
            'target_id': target_id, 'token': cache_token
        }
        return JsonResponse(json_resp, status=200)

    except Exception as e:
        raise e
        return JsonResponse({"msg": repr(e)}, status=500)


# get feedback and return result (without syntax, without behavior)
def send_feedback_nn_helper(kwargs):
    loc_id = kwargs['locid']
    location = m.Location.objects.get(id=loc_id)

    # target action to automate
    dev_c = kwargs['device']
    command_c = kwargs['command']
    target_action = pv_clause_to_autotap_statement(dev_c, command_c['capability'], 
                                                   command_c['parameter'], command_c['value'])

    # get current rules related to the target action
    rule_set = m.Rule.objects.filter(location=location).order_by('id')
    orig_tap_list = [translate_rule_into_autotap_tap(rule) for rule in rule_set 
                     if translate_rule_into_autotap_tap(rule).action == target_action]

    # get trace
    trace = get_trace_for_location(location)
    # select related caps
    template_dict = generate_all_device_templates()
    target_zone = m.Device.objects.get(id=dev_c['id']).zone
    cap_rst = generate_cap_sensor_same_zone(target_zone)

    time_event_cond_list, revert_list = extractTriggerCases(
        trace, target_action, tap_list=orig_tap_list, pre_time_span=datetime.timedelta(seconds=settings.MAX_AUTOMATION_TIME))
    cap_trigger = listTimingCandidates(
        trace, target_action, 6, template_dict=template_dict, cap_rst=cap_rst)
    cap_trigger = cap_trigger[:3]
    cap_condition = listRelatedCandidates(trace, target_action, 3, template_dict=template_dict, cap_rst=cap_rst)
    cap_condition_rev = listRelatedRevCandidates(trace, time_event_cond_list, 
                                                 revert_list, target_action, 2, cap_rst=cap_rst, 
                                                 cap_skip={cap for cap, _ in cap_condition},
                                                 template_dict=template_dict)
    
    cap_list = [cap for cap, _, _ in cap_trigger]
    cap_list = cap_list + [cap for cap, _ in cap_condition] + [cap for cap, _ in cap_condition_rev]
    cap_list = list(set(cap_list))

    cap_time_list = [(cap, time) for cap, time, _ in cap_trigger if time > 1]
    cap_trigger_list = [cap for cap, _, _ in cap_trigger]
    cap_condition_list = [cap for cap, _ in cap_condition] + [cap for cap, _ in cap_condition_rev]
    cap_condition_list = list(set(cap_condition_list))

    target_cap = target_action.split('=')[0]
    if target_cap not in cap_list:
        cap_list.append(target_cap)

    # add all caps shown up to cap_list
    tap_cap_list = get_all_caps_in_taps(orig_tap_list)
    for cap in tap_cap_list:
        if cap not in cap_list:
            cap_list.append(cap)
    # add all caps shown up in cond to cap_condition_list
    tap_cond_cap_list = get_all_caps_in_taps(orig_tap_list, only_cond=True)
    for cap in tap_cond_cap_list:
        if cap not in cap_condition_list:
            cap_condition_list.append(cap)
    tap_cap_time_list, tap_clock_list = get_time_information_from_taps(orig_tap_list)

    # cut off unrelated caps from trace
    trace = getSubTraceBasedOnCaps(trace, cap_list)

    # we should enhance trace with the timing information from the rules
    trace = enhanceTraceWithTiming(trace, tap_cap_time_list, '*')
    trace = enhanceTraceWithClock(trace, tap_clock_list)

    # extract fn_episode_list
    fn_episode_list = extractEpisodes(trace, target_action, 
                                      pre_time_span=datetime.timedelta(seconds=settings.PRE_TIME), 
                                      post_time_span=datetime.timedelta(seconds=settings.POST_TIME))

    # Gather time_event_cond_list, and revert_list
    # it contains while automated actions should be reverted (fp_feedback)
    time_event_cond_list, revert_list = extractTriggerCases(
        trace, target_action, tap_list=orig_tap_list, pre_time_span=datetime.timedelta(seconds=settings.MAX_AUTOMATION_TIME))

    info_dict = {
        'trace': trace,
        'fn_episode_list': fn_episode_list,
        'time_event_cond_list': time_event_cond_list,
        'revert_list': revert_list,
        'orig_tap_list': orig_tap_list,
        'cap_time_list': cap_time_list,
        'cap_list': cap_list,
        'cap_condition_list': cap_condition_list,
        'cap_trigger_list': cap_trigger_list
    }

    return info_dict

# get feedback and return result (without syntax, with behavior)
def send_feedback_nf_helper(kwargs):
    token = kwargs['request_token']
    # when receiving this call, we should already have caches in db
    cache_entry = cache.get(token)

    # gather information
    target_action = cache_entry['target_action']
    cap_list = cache_entry['cap_list']
    cap_trigger_list = cache_entry['cap_trigger_list']
    cap_condition_list = cache_entry['cap_condition_list']
    cap_time_list = cache_entry['cap_time_list']
    template_dict = cache_entry['template_dict']
    orig_tap_list = cache_entry['orig_tap_list']
    trace = cache_entry['trace']
    episode_list = cache_entry['episode_list']
    episodes_unactuated_list = cache_entry['episodes_unactuated_list']

    # update cache for potential alt usage
    cache_entry['fn_feedbacks'] = kwargs['fn_feedbacks']
    cache_entry['fp_feedbacks'] = kwargs['fp_feedbacks']
    cache.set(token, cache_entry)

    ############################################
    # generate fn_episode_list from fn_feedbacks
    ############################################
    fn_feedbacks = kwargs['fn_feedbacks']
    fn_times = [datetime.datetime.strptime(entry['time'], '%Y-%m-%d %H:%M:%S') for entry in fn_feedbacks]
    fn_episode_list = []
    for fn_time in fn_times:
        clip = generate_clip(trace, 
                             fn_time-datetime.timedelta(seconds=settings.PRE_TIME), 
                             fn_time+datetime.timedelta(seconds=settings.POST_TIME))
        fn_episode_list.append(clip)
    # mask_tap_list = synthesizeRuleGeneral(fn_episode_list, target_action, learning_rate=settings.LEARNING_RATE_SYN,
    #                                       variable_list=cap_list, trig_var_list=cap_trigger_list,
    #                                       cond_var_list=cap_condition_list,
    #                                       timing_cap_list=cap_time_list,
    #                                       template_dict=template_dict, tap_list=orig_tap_list)
    
    ############################################
    # generate time_event_cond_list and 
    # revert_list from fp_feedbacks
    ############################################
    fp_feedbacks = kwargs['fp_feedbacks']
    reference_dict = cache_entry['reference_dict']
    other_reference_set = {key for key in reference_dict if reference_dict[key] >= 0}
    other_reference_set_unactuated = {key for key in reference_dict if reference_dict[key] < 0}
    fp_indices = []
    fp_indices_unactuated = []
    other_indices = []
    for fp_fb in fp_feedbacks:
        log_id = fp_fb['log_id']
        time_str = fp_fb['time_str']
        entry_id = fp_fb['entry_id']
        # TODO: what about clock event triggered?
        # we need to check what event caused this action
        if (log_id, time_str, entry_id) in reference_dict:
            action_id = reference_dict[(log_id, time_str, entry_id)]
            if action_id >= 0:
                fp_indices.append((log_id, action_id))
                other_reference_set.remove((log_id, time_str, entry_id))
            else:
                fp_indices_unactuated.append((log_id, -action_id-1))
                other_reference_set_unactuated.remove((log_id, time_str, entry_id))
            
    for log_id, time_str, entry_id in other_reference_set:
        other_indices.append((log_id, reference_dict[(log_id, time_str, entry_id)]))

    time_event_cond_list, revert_list = extractTriggeringEvent(
        episode_list, target_action, fp_indices, other_indices, orig_tap_list, pre_time_span=datetime.timedelta(seconds=settings.MAX_AUTOMATION_TIME))

    # for triggered events that are not actuated, we put feedback into time_event_cond_list and revert list
    for log_id, event_id in fp_indices_unactuated:
        time_event_cond_list.append(episodes_unactuated_list[log_id][event_id])
        revert_list.append(True)
    
    for log_id, time_str, entry_id in other_reference_set_unactuated:
        event_id = -reference_dict[(log_id, time_str, entry_id)]-1
        time_event_cond_list.append(episodes_unactuated_list[log_id][event_id])
        revert_list.append(False)

    info_dict = {
        'trace': trace,
        'fn_episode_list': fn_episode_list,
        'time_event_cond_list': time_event_cond_list,
        'revert_list': revert_list,
        'orig_tap_list': orig_tap_list,
        'cap_time_list': cap_time_list,
        'cap_list': cap_list,
        'cap_condition_list': cap_condition_list,
        'cap_trigger_list': cap_trigger_list
    }

    return info_dict


# get feedback and return result (without syntax, with behavior)
# however, the user's selection for fn vs fp was wrong
# i.e. we need to translate "light should be off" into "light should not be turned on"
def send_feedback_nf_alt_helper(kwargs):
    token = kwargs['request_token']
    # when receiving this call, we should already have caches in db
    cache_entry = cache.get(token)

    # gather information
    target_action = cache_entry['target_action']
    cap_list = cache_entry['cap_list']
    cap_trigger_list = cache_entry['cap_trigger_list']
    cap_condition_list = cache_entry['cap_condition_list']
    cap_time_list = cache_entry['cap_time_list']
    full_tap_list = cache_entry['full_tap_list']
    trace = cache_entry['trace']
    episode_list = cache_entry['episode_list']

    # get the opposite target action
    target_action = generateOppositeAction(target_action)

    # we need to re-fetch the rules
    orig_tap_list = [tap for tap in full_tap_list if tap.action == target_action]

    ############################################
    # turn fn_feedbacks into fp_feedbacks
    # i.e., time_event_cond_list, revert_list
    ############################################
    fn_feedbacks = cache_entry['fn_feedbacks']
    fn_times = [datetime.datetime.strptime(entry['time'], '%Y-%m-%d %H:%M:%S') for entry in fn_feedbacks]
    time_event_cond_list, revert_list = extractTriggerCasesAlt(
        trace, target_action, orig_tap_list, fn_times, 
        pre_time_span=datetime.timedelta(seconds=settings.MAX_AUTOMATION_TIME), 
        revert_time_span=datetime.timedelta(seconds=settings.REVERT_TIME_ALT))
    
    fn_episode_list = []
    for fn_time in fn_times:
        clip = generate_clip(trace, 
                             fn_time-datetime.timedelta(seconds=settings.PRE_TIME), 
                             fn_time+datetime.timedelta(seconds=settings.POST_TIME))
        fn_episode_list.append(clip)
    
    ############################################
    # turn fp_feedbacks into fn_feedbacks
    # i.e., fn_episode_list
    ############################################
    fp_feedbacks = cache_entry['fp_feedbacks']
    reference_dict = cache_entry['reference_dict']
    alt_fn_times = []
    for fp_fb in fp_feedbacks:
        log_id = fp_fb['log_id']
        time_str = fp_fb['time_str']
        entry_id = fp_fb['entry_id']
        if (log_id, time_str, entry_id) in reference_dict:
            action_id = reference_dict[(log_id, time_str, entry_id)]
            if action_id > 0:
                action_time = episode_list[log_id].actions[action_id][0]
                alt_fn_times.append(action_time)
    
    fn_episode_list = []
    for fn_time in alt_fn_times:
        clip = generate_clip(trace, 
                             fn_time-datetime.timedelta(seconds=settings.PRE_TIME), 
                             fn_time+datetime.timedelta(seconds=settings.POST_TIME))
        fn_episode_list.append(clip)

    info_dict = {
        'trace': trace,
        'fn_episode_list': fn_episode_list,
        'time_event_cond_list': time_event_cond_list,
        'revert_list': revert_list,
        'orig_tap_list': orig_tap_list,
        'cap_time_list': cap_time_list,
        'cap_list': cap_list,
        'cap_condition_list': cap_condition_list,
        'cap_trigger_list': cap_trigger_list,
        'target_action': target_action
    }

    return info_dict


# get feedback and return result (with syntax, without behavior)
def send_feedback_sn_helper(kwargs):
    # get location
    loc_id = kwargs['locid']
    location = m.Location.objects.get(id=loc_id)

    # target action to automate
    dev_c = kwargs['device']
    command_c = kwargs['command']
    target_action = pv_clause_to_autotap_statement(dev_c, command_c['capability'], 
                                                   command_c['parameter'], command_c['value'])

    # get current rules related to the target action
    rule_set = m.Rule.objects.filter(location=location).order_by('id')
    orig_tap_list = [translate_rule_into_autotap_tap(rule) for rule in rule_set 
                     if translate_rule_into_autotap_tap(rule).action == target_action]

    # get trace
    trace = get_trace_for_location(location)
    # select related caps
    template_dict = generate_all_device_templates()
    target_zone = m.Device.objects.get(id=dev_c['id']).zone
    cap_rst = generate_cap_sensor_same_zone(target_zone)

    time_event_cond_list, revert_list = extractTriggerCases(
        trace, target_action, tap_list=orig_tap_list, pre_time_span=datetime.timedelta(seconds=settings.MAX_AUTOMATION_TIME))
    cap_trigger = listTimingCandidates(
        trace, target_action, 6, template_dict=template_dict, cap_rst=cap_rst)
    cap_trigger = cap_trigger[:3]
    cap_condition = listRelatedCandidates(trace, target_action, 3, template_dict=template_dict, cap_rst=cap_rst)
    cap_condition_rev = listRelatedRevCandidates(trace, time_event_cond_list, 
                                                 revert_list, 2, cap_rst=cap_rst, 
                                                 cap_skip={cap for cap, _ in cap_condition})
    
    cap_list = [cap for cap, _, _ in cap_trigger]
    cap_list = cap_list + [cap for cap, _ in cap_condition] + [cap for cap, _ in cap_condition_rev]
    cap_list = list(set(cap_list))

    cap_time_list = [(cap, time) for cap, time, _ in cap_trigger if time > 1]
    cap_trigger_list = [cap for cap, _, _ in cap_trigger]
    cap_condition_list = [cap for cap, _ in cap_condition] + [cap for cap, _ in cap_condition_rev]
    cap_condition_list = list(set(cap_condition_list))

    target_cap = target_action.split('=')[0]
    if target_cap not in cap_list:
        cap_list.append(target_cap)
    
    # get current rules related to the target action
    rule_set = m.Rule.objects.filter(location=location).order_by('id')
    orig_tap_list = [translate_rule_into_autotap_tap(rule) for rule in rule_set 
                     if translate_rule_into_autotap_tap(rule).action == target_action]

    # add all caps shown up to cap_list
    tap_cap_list = get_all_caps_in_taps(orig_tap_list)
    for cap in tap_cap_list:
        if cap not in cap_list:
            cap_list.append(cap)
    # add all caps shown up in cond to cap_condition_list
    tap_cond_cap_list = get_all_caps_in_taps(orig_tap_list, only_cond=True)
    for cap in tap_cond_cap_list:
        if cap not in cap_condition_list:
            cap_condition_list.append(cap)
    tap_cap_time_list, tap_clock_list = get_time_information_from_taps(orig_tap_list)

    # cut off unrelated caps from trace
    trace = getSubTraceBasedOnCaps(trace, cap_list)

    # we should enhance trace with the timing information from the rules
    trace = enhanceTraceWithTiming(trace, tap_cap_time_list, '*')
    trace = enhanceTraceWithClock(trace, tap_clock_list)

    # extract fn_episode_list
    fn_episode_list = extractEpisodes(trace, target_action, 
                                      pre_time_span=datetime.timedelta(seconds=settings.PRE_TIME), 
                                      post_time_span=datetime.timedelta(seconds=settings.POST_TIME))

    # Gather time_event_cond_list, and revert_list
    # it contains while automated actions should be reverted (fp_feedback)
    time_event_cond_list, revert_list = extractTriggerCases(
        trace, target_action, tap_list=orig_tap_list, pre_time_span=datetime.timedelta(seconds=settings.MAX_AUTOMATION_TIME))

    info_dict = {
        'trace': trace,
        'fn_episode_list': fn_episode_list,
        'time_event_cond_list': time_event_cond_list,
        'revert_list': revert_list,
        'orig_tap_list': orig_tap_list,
        'cap_time_list': cap_time_list,
        'cap_list': cap_list,
        'cap_condition_list': cap_condition_list,
        'cap_trigger_list': cap_trigger_list
    }

    return info_dict


def send_feedback(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    loc_id = kwargs['locid']
    err_json, status = check_access_to_location(request, loc_id)
    if is_error(status):
        return JsonResponse(err_json, status=status)
    
    # gather shared information for all types of interfaces
    location = m.Location.objects.get(id=loc_id)
    if location.is_template:
        mode = request.session['mode']
    else:
        mode = location.user.mode

    template_dict = generate_all_device_templates()
    rule_set = m.Rule.objects.filter(location=location).order_by('id')
    dev_c = kwargs['device']
    command_c = kwargs['command']
    target_action = pv_clause_to_autotap_statement(dev_c, command_c['capability'], 
                                                   command_c['parameter'], command_c['value'])
    orig_rules = [backend_to_frontend_view(rule) for rule in rule_set 
                  if translate_rule_into_autotap_tap(rule).action == target_action]

    is_alt = False
    # gather things we need for synthesis for different types of interfaces
    if mode == m.User.NOSYN_FEEDBACK:
        is_alt = 'is_alt' in kwargs and kwargs['is_alt']  # check if this is for alternative feedback
        if not is_alt:
            info_dict = send_feedback_nf_helper(kwargs)
        else:
            # we need to re-generate things
            target_action = generateOppositeAction(target_action)
            orig_rules = [backend_to_frontend_view(rule) for rule in rule_set 
                          if translate_rule_into_autotap_tap(rule).action == target_action]
            info_dict = send_feedback_nf_alt_helper(kwargs)
        syntax_fb_entries = None
    elif mode == m.User.NOSYN_NOFEEDBACK:
        info_dict = send_feedback_nn_helper(kwargs)
        syntax_fb_entries = None
    elif mode == m.User.SYN_FEEDBACK:
        syntax_fb_entries = kwargs['syntax_feedbacks']
        pass
    elif mode == m.User.SYN_NOFEEDBACK:
        info_dict = send_feedback_sn_helper(kwargs)
        syntax_fb_entries = kwargs['syntax_feedbacks']
    else:  # control
        pass

    # Update cache for the visualization
    # info_dict will later be stored in the cache
    while True:
        cache_token = get_random_string(length=128)
        if cache.get(cache_token) is None:
            break
    info_dict["target_action"] = target_action
    
    trace = info_dict['trace']
    fn_episode_list = info_dict['fn_episode_list']
    time_event_cond_list = info_dict['time_event_cond_list']
    revert_list = info_dict['revert_list']
    orig_tap_list = info_dict['orig_tap_list']
    cap_time_list = info_dict['cap_time_list']
    cap_list = info_dict['cap_list']
    cap_condition_list = info_dict['cap_condition_list']
    cap_trigger_list = info_dict['cap_trigger_list']

    patches = []
    patch_masks = []
    new_patches, new_patch_masks = fixByChangingCondition(
        trace, fn_episode_list, time_event_cond_list, revert_list, orig_tap_list, target_action,
        learning_rate_fn=settings.LEARNING_RATE_SYN, 
        learning_rate_fp=settings.LEARNING_RATE_REVERT, 
        learning_rate_tp=settings.LEARNING_RATE_REMAINING, 
        variable_list=cap_list, 
        cond_var_list=cap_condition_list, template_dict=template_dict,
        syntax_fb_entries=syntax_fb_entries)
    patches += new_patches
    patch_masks += new_patch_masks
    new_patches, new_patch_masks = fixByAddingOrDeletingRule(
        trace, fn_episode_list, time_event_cond_list, revert_list, orig_tap_list, 
        cap_time_list, target_action, 
        learning_rate_fn=settings.LEARNING_RATE_SYN, 
        learning_rate_fp=settings.LEARNING_RATE_REVERT, 
        learning_rate_tp=settings.LEARNING_RATE_REMAINING, 
        variable_list=cap_list, 
        cond_var_list=cap_condition_list, trig_var_list=cap_trigger_list, template_dict=template_dict,
        syntax_fb_entries=syntax_fb_entries)
    patches += new_patches
    patch_masks += new_patch_masks
    
    score_patch_mask_list = []
    # calculated because we want to remove original triggered events from "new introduced" actions
    existing_time_points = set(getTapListTriggerTime(trace, orig_tap_list, for_vis=True))
    for patch, mask in zip(patches, patch_masks):
        new_tap_list = apply_tap_patch(orig_tap_list, patch)
        score, meta = calcScoreTapDebug(new_tap_list, trace, mask, revert_list, time_event_cond_list, fn_episode_list, existing_time_points)
        patch['meta'] = {'FP_fixed': meta['FP_fixed'], 'FN_fixed': meta['FN_fixed'],
            'TP_cancelled': meta['TP_cancelled'], 'new_introduced': meta['new_introduced']}
        complexity = tap_patch_complexity(patch)
        score = (score, -complexity)
        score_patch_mask_list.append((score, patch, mask))
    
    score_patch_mask_list = sorted(score_patch_mask_list, key = lambda x: x[0], reverse=True)
    patches = [patch for _, patch, _ in score_patch_mask_list]
    patch_masks = [mask for _, _, mask in score_patch_mask_list]
    info_dict['patches'] = deepcopy(patches)
    info_dict['patch_masks'] = deepcopy(patch_masks)
    info_dict['existing_time_points'] = existing_time_points
    patches = [patch_to_frontend_view(patch, location) for patch in patches]

    # based on the mask, put patches into clusters
    result_list = cluster_patches(patches, patch_masks)

    # Calculate the score of rules (for ranking)
    # mask_score_tap_list = []
    # for rule_mask, tap in mask_tap_list:
    #     score, TP, FP, R = calcScoreEnhanced(trace, target_action, tap, 
    #                                          pre_time_span=settings.PRE_TIME, 
    #                                          post_time_span=settings.POST_TIME)
    #     mask_score_tap_list.append((rule_mask, score, tap, TP, FP, R))

    # # Cluster the rules based on their mask
    # mask_score_tap_cluster, orig_tap_cluster = cluster_rules(mask_score_tap_list, None)
    # for cluster in mask_score_tap_cluster:
    #     for rule_d in cluster:
    #         rule_d['mode'] = 'add-rule'

    # update cache
    cache.add(cache_token, info_dict)

    json_resp = {}
    # json_resp['rules'] = mask_score_tap_cluster
    json_resp['orig_rules'] = orig_rules
    json_resp['patches'] = result_list
    json_resp['trace_meta'] = getTraceMeta(trace)
    json_resp['vis_token'] = cache_token

    return JsonResponse(json_resp, status=200)


def get_rules_for_syntax(request):
    kwargs = json.loads(request.body.decode('utf-8'))
    loc_id = kwargs['locid']
    err_json, status = check_access_to_location(request, loc_id)
    if is_error(status):
        return JsonResponse(err_json, status=status)
    
    location = m.Location.objects.get(id=loc_id)

    # get the target action
    dev_c = kwargs['device']
    command_c = kwargs['command']
    target_action = pv_clause_to_autotap_statement(dev_c, command_c['capability'], 
                                                    command_c['parameter'], command_c['value'])

    rule_set = m.Rule.objects.filter(location=location).order_by('id')
    rule_set = [rule for rule in rule_set if translate_rule_into_autotap_tap(rule).action == target_action]

    # translate the rules to frontend format
    rules_frontend = [backend_to_frontend_view(rule) for rule in rule_set]

    json_resp = {}
    json_resp['rules'] = rules_frontend
    return JsonResponse(json_resp, status=200)


def getepisode_manual(request):
    if request.user.is_authenticated and request.user.is_superuser:
        kwargs = json.loads(request.body.decode('utf-8'))
        loc_id = kwargs['locid']
        entities = kwargs['entities']
        start_time_str = kwargs['start_time']
        end_time_str = kwargs['end_time']

        location = m.Location.objects.get(id=loc_id)
        trace = get_trace_for_location(location)
        rev_map = generate_reverse_template(loc=location)

        start_time = datetime.datetime.strptime(start_time_str, '%Y-%m-%d %H:%M')
        end_time = datetime.datetime.strptime(end_time_str, '%Y-%m-%d %H:%M')

        cap_list = []
        for entity in entities:
            dev_id = entity['device']['id']
            cap_id = entity['capability']['id']
            param_id = entity['parameter']['id']
            dev = m.Device.objects.get(id=dev_id)
            cap = m.Capability.objects.get(id=cap_id)
            param = m.Parameter.objects.get(id=param_id)
            cap_list.append(generate_autotap_name_for_dev_cap_param(dev, cap, param))
        
        episode = generate_clip(trace, start_time, end_time)
        episode = getSubTraceBasedOnCaps(episode, cap_list)

        clip = translate_time_clip_debug(episode, -1, rev_map)

        trace_vis = parse_trace_new([clip])[0]
        
        device_list = [rev_map[cap][0].name for cap in episode.system.getFieldNameList()]
        capability_list = [rev_map[cap][1].name for cap in episode.system.getFieldNameList()]

        json_resp = {'log': trace_vis, 'dev_list': device_list, 'cap_list': capability_list} # parse log as HTML

        return JsonResponse(json_resp, status=200)
    else:
        return JsonResponse({"msg": "Please log in as superuser first!"}, status=401)


def get_revert_for_location(request):
    if request.user.is_authenticated and request.user.is_superuser:
        kwargs = json.loads(request.body.decode('utf-8'))
        loc_id = kwargs['loc_id']
        location = m.Location.objects.get(id=loc_id)
        template_dict = generate_all_device_templates()
        boolean_map = generate_boolean_map()
        trace = get_trace_for_location(location)
        devs = m.Device.objects.filter(location=location)
        rule_set = m.Rule.objects.filter(st_installed_app_id=location.st_installed_app_id).order_by('id')
        orig_tap_list = [translate_rule_into_autotap_tap(rule, use_tick_header=False) for rule in rule_set]
        cap_time_list = []
        for tap in orig_tap_list:
            cap_time_list += generate_cap_time_list_from_tap(tap)
        cap_time_list = list(set(cap_time_list))
        trace = enhanceTraceWithTiming(trace, cap_time_list, '*')

        commands = []
        devices = []
        for dev in devs:
            command_tup_list = get_dev_commands(dev, trace=trace, template_dict=template_dict, 
                                                boolean_map=boolean_map, orig_tap_list=orig_tap_list)
            for cap, param, val, count, covered, reverted in command_tup_list:
                if reverted:
                    command = {
                        "capability": {"id": cap.id, "name": cap.name, "label": cap.commandlabel}, 
                        "parameter": {"id": param.id, "name": param.name, "type": param.type, "values": get_param_vals(param)}, 
                        "value": val, "count": count, "covered": covered, 'reverted': reverted
                    }
                    commands.append(command)
        
        return JsonResponse({'commands': commands}, status=200)
    else:
        return JsonResponse({"msg": "You need to log in as a superuser!"}, status=401)


def get_revert_action(request):
    if request.user.is_authenticated and request.user.is_superuser:
        kwargs = json.loads(request.body.decode('utf-8'))
        device_id = kwargs['device']['id']
        device = m.Device.objects.get(id=device_id)
        location = device.location
        trace = get_trace_for_location(location)
        target_action = pv_clause_to_autotap_statement(kwargs['device'], kwargs['command']['capability'], 
                                                       kwargs['command']['parameter'], kwargs['command']['value'])

        # Generate items for translation
        rev_map = generate_reverse_template(loc=location)

        # Enhance trace with timing
        rule_set = m.Rule.objects.filter(st_installed_app_id=location.st_installed_app_id).order_by('id')
        orig_tap_list = [translate_rule_into_autotap_tap(rule, use_tick_header=False) for rule in rule_set]
        orig_tap_list = [tap for tap in orig_tap_list if tap.action == target_action]
        cap_time_list = []
        for tap in orig_tap_list:
            cap_time_list += generate_cap_time_list_from_tap(tap)
        cap_time_list = list(set(cap_time_list))
        trace = enhanceTraceWithTiming(trace, cap_time_list, '*')

        # Get dev/cap names
        device_list = [rev_map[cap][0].name for cap in trace.system.getFieldNameList()]
        capability_list = [rev_map[cap][1].name for cap in trace.system.getFieldNameList()]
        target_dev_cap_id = trace.system.getFieldNameList().index(target_action.split('=')[0])

        # Extract revert cases
        time_window = datetime.timedelta(seconds=settings.VIS_DEBUG)
        revert_time_list = extractRevertCases(trace, target_action)
        time_dict_list = []

        for time in revert_time_list:
            episode = generate_clip(trace, time-time_window, time+time_window)
            event_id = episode.actions.index((time, target_action))
            time_dict = translate_time_clip_debug(episode, event_id, rev_map)
            time_dict_list.append(time_dict)

        trace_vis_list = parse_trace_new(time_dict_list)
        json_resp = {'log_list': trace_vis_list, 'dev_list': device_list, 
                     'cap_list': capability_list, 'target_id': target_dev_cap_id}
        return JsonResponse(json_resp, status=200)
    else:
        return JsonResponse({"msg": "You need to log in as a superuser!"}, status=401)


def get_manual_changes(request):
    if request.user.is_authenticated and request.user.is_superuser:
        kwargs = json.loads(request.body.decode('utf-8'))
        location = m.Location.objects.get(id=kwargs['loc_id'])
        all_records = m.Record.objects.filter(typ='edit_rule', location=location).order_by('timestamp')
        resp_list = []
        for record in all_records:
            if record.response:
                resp = json.loads(record.response)

                # translate from utc time to local time
                tf = TimezoneFinder()
                location_tz = tf.timezone_at(lng=location.lon, lat=location.lat)
                utc_time = record.timestamp
                utc_time = utc_time.replace(tzinfo=utc)
                local_time = utc_time.astimezone(timezone(location_tz))
                resp['time'] = local_time
                if 'loc_id' in resp and resp['loc_id'] == location.id:
                    resp_list.append(resp)

        json_resp = {'resp_list': resp_list}
        return JsonResponse(json_resp, status=200)
    else:
        return JsonResponse({"msg": "You need to log in as a superuser!"}, status=401)


def get_debug_pages(request):
    if request.user.is_authenticated and request.user.is_superuser:
        kwargs = json.loads(request.body.decode('utf-8'))
        location = m.Location.objects.get(id=kwargs['loc_id'])
        all_records = m.Record.objects.filter(typ__in=('debug_first', 'debug_followup'), location=location).order_by('timestamp')
        resp_list = []
        for record in all_records:
            if record.response:
                resp = json.loads(record.response)
                resp['time'] = str(record.timestamp)
                resp_list.append(resp)
        json_resp = {'resp_list': resp_list}
        return JsonResponse(json_resp, status=200)
    else:
        return JsonResponse({"msg": "You need to log in as a superuser!"}, status=401)

from autotapta.model.Trace import Trace
from autotapmc.model.Tap import Tap
from autotapta.analyze.Formula import checkEventAgainstTrigger
from autotapta.analyze.Analyze import extractTimePoints, getTrigTimeEventCond
import math
import datetime


def getRuleCoverage(trigger_time_list, actual_time_list, time_span: int=1200):
    TP = 0
    for action_time in actual_time_list:
        for trigger_time in trigger_time_list:
            if abs(trigger_time-action_time) < time_span:
                TP += 1
                break
    return TP


def getInfoFromTimingEnhanced(trigger_time_list, actual_time_list, pre_time_span, post_time_span):
    latency_list = list()

    TP = 0
    FP = 0

    action_covered_list = [False] * len(actual_time_list)
    trigger_tp_list = [False] * len(trigger_time_list)
    latency_list = []

    for index_a in range(len(actual_time_list)):
        action_time = actual_time_list[index_a]
        for index_t in range(len(trigger_time_list)):
            trigger_time = trigger_time_list[index_t]
            if action_time-pre_time_span <= trigger_time < action_time+post_time_span:
                # TP
                action_covered_list[index_a] = True
                trigger_tp_list[index_t] = True
                latency_list.append(trigger_time - action_time)
    
    TP = sum(action_covered_list)
    FP = len(trigger_tp_list) - sum(trigger_tp_list)
    latency = None if not latency_list else sum(latency_list) * 1.0 / len(latency_list)
    
    return TP, FP, latency


def getInfoFromTiming(trigger_time_list, actual_time_list, time_span: int=1200):
    latency_list = list()

    TP = 0
    FP = 0
    for rule_time in trigger_time_list:
        found_index = None
        min_diff = float('inf')
        for action_time, index in zip(actual_time_list, range(len(actual_time_list))):
            if abs(action_time - rule_time) < min_diff:
                # TP = TP + 1
                found_index = index
                min_diff = abs(action_time - rule_time)
                min_diff_raw = rule_time - action_time
        if found_index and min_diff < time_span:
            TP = TP + 1
            actual_time_list.pop(found_index)
            latency_list.append(min_diff_raw)
        else:
            FP = FP + 1
    latency = None if not latency_list else sum(latency_list) * 1.0 / len(latency_list)

    return TP, FP, latency


def testTimeInRange(time, start_time, end_time):
    """
    time should be datetime.time object,
    start_time and end_time should be datetime.datetime objects
    """
    start_date = start_time.date()
    end_date = end_time.date()
    current_date = start_time.date()
    while current_date <= end_date:
        st = start_time.time() if current_date == start_date else datetime.time.min
        en = end_time.time() if current_date == end_date else datetime.time.max
        if (st < time <= en and current_date == start_date) or (st <= time <= en and current_date != start_date):
            return True, datetime.datetime.combine(current_date, time)
        current_date += datetime.timedelta(days=1)
    return False, None


def checkTapTriggeredWithAction(tap, system, action, time=None):
    """
    We need to have system at the state right before action
    """
    if action == tap.trigger and system.tapConditionSatisfied(tap, time=time):
        return True
    else:
        return False


def checkTapTriggeredWithinTime(tap, system, start_time, end_time):
    """
    We need to have system at the state right before action
    """
    if tap.trigger.startswith('clock.clock_time'):
        time_secs = int(tap.trigger.split('=')[1])
        secs = time_secs % 60
        time_secs //= 60
        minutes = time_secs % 60
        time_secs //= 60
        hours = time_secs
        rule_time = datetime.time(hour=hours, minute=minutes, second=secs)
    else:
        rule_time = None
    
    if rule_time is None:
        return False

    is_inrange, _ = testTimeInRange(rule_time, start_time, end_time)
    if is_inrange and system.tapConditionSatisfied(tap):
        return True
    else:
        return False


def checkIfEpisodeCovered(episode, tap_list, target_action):
    if not episode.actions:
        raise Exception('Empty trace not accepted by calcScore')

    previous_time = episode.start_time
    system = episode.system
    system.restoreFromStateVector(episode.initial_state)

    for time_action, pre_condition, is_ext in zip(episode.actions, episode.pre_condition, episode.is_ext_list):
        time, action = time_action
        
        triggered_action = None
        for tap in tap_list:
            if checkTapTriggeredWithinTime(tap, system, previous_time, time) and tap.action == target_action:
                triggered_action = tap.action
                break
            if checkTapTriggeredWithAction(tap, system, action, time) and tap.action == target_action:
                triggered_action = tap.action
                break
        
        if action != target_action and '*' not in action and '#' not in action and is_ext:
            system.applyAction(action)
        if triggered_action is not None:
            system.applyAction(triggered_action)
        
        previous_time = time
    
    if episode.end_time is not None:
        triggered_action = None
        for tap in tap_list:
            if checkTapTriggeredWithinTime(tap, system, previous_time, episode.end_time) and tap.action == target_action:
                triggered_action = tap.action
                break
        if triggered_action is not None:
            system.applyAction(triggered_action)
    
    if system.conditionSatisfied(target_action):
        return True
    else:
        return False


# check times when taps are triggered in the trace
# this function assumes that all taps in tap_list trigger the target action
# this function just check triggered actions over the orig trace without considering changes applied
# return datetimes
def getTapListTriggerTime(trace, tap_list, for_vis=False):
    if not trace.actions:
        raise Exception('Empty trace not accepted by calcScore')

    if not tap_list:
        return []
    
    time_event_cond_list = getTrigTimeEventCond(trace, tap_list, for_vis)
    return [time for time, _, _ in time_event_cond_list]


def getRealActionTimeAndRuleTriggerTime(trace, tap, target_action, in_secs=True, check_enable=True, revert_span=120):
    if not trace.actions:
        raise Exception('Empty trace not accepted by calcScore')

    time_points = extractTimePoints(trace, target_action, datetime.timedelta(seconds=revert_span))
    start_time = trace.start_time if trace.start_time is not None else trace.actions[0][0]

    target_action_timing = [(t-start_time).total_seconds() for t in time_points]
    rule_trigger_timing = []

    if tap.trigger.startswith('clock.clock_time'):
        time_secs = int(tap.trigger.split('=')[1])
        secs = time_secs % 60
        time_secs //= 60
        minutes = time_secs % 60
        time_secs //= 60
        hours = time_secs
        rule_time = datetime.time(hour=hours, minute=minutes, second=secs)
    else:
        rule_time = None
    
    previous_time = start_time
    system = trace.system
    system.restoreFromStateVector(trace.initial_state)
    for time_action, _, is_ext in zip(trace.actions, trace.pre_condition, trace.is_ext_list):
        time, action = time_action
        # if action == target_action and is_ext:
        #     if in_secs:
        #         target_action_timing.append((time-start_time).total_seconds())
        #     else:
        #         target_action_timing.append(time)

        triggered_action = None
        if rule_time is not None:
            is_inrange, trigger_time = testTimeInRange(rule_time, previous_time, time)
            if is_inrange and trace.system.tapConditionSatisfied(tap) and \
                (not check_enable or not trace.system.conditionSatisfied(tap.action)):
                if in_secs:
                    rule_trigger_timing.append((trigger_time-start_time).total_seconds())
                else:
                    rule_trigger_timing.append(trigger_time)
                triggered_action = tap.action
        else:
            if checkEventAgainstTrigger(action, tap.trigger) and trace.system.tapConditionSatisfied(tap) and \
                    (not check_enable or not trace.system.conditionSatisfied(tap.action)) and \
                    ('*' in tap.trigger or not trace.system.conditionSatisfied(tap.trigger)):
                if in_secs:
                    rule_trigger_timing.append((time-start_time).total_seconds())
                else:
                    rule_trigger_timing.append(time)
                triggered_action = tap.action
        if action != target_action and '*' not in action and '#' not in action and is_ext:
            system.applyAction(action)
        if triggered_action is not None:
            system.applyAction(triggered_action)

        previous_time = time

    if trace.end_time is not None:
        if rule_time is not None:
            last_action = trace.actions[-1][1]
            pre_condition = trace.pre_condition[-1]
            trace.system.restoreFromStateVector(pre_condition)
            if '*' not in last_action and '#' not in last_action:
                trace.system.applyAction(last_action)
                pre_condition = trace.system.saveToStateVector()
            is_inrange, trigger_time = testTimeInRange(rule_time, previous_time, time)
            if is_inrange and trace.system.tapConditionSatisfied(tap, pre_condition) and \
                (not check_enable or not trace.system.conditionSatisfied(tap.action, pre_condition)):
                if in_secs:
                    rule_trigger_timing.append((trigger_time-start_time).total_seconds())
                else:
                    rule_trigger_timing.append(trigger_time)
    
    return target_action_timing, rule_trigger_timing


def extractOrigNewTriggerTimes(trace: Trace, target_action, orig_tap_list, new_tap_cluster):
    """
    extract three time lists:
        0) times when user applies manual actions
        1) times when orig rules triggered the action
        2) times when orig rules would have triggered the action (rules might be added after the times)
        3) times when each cluster of new rules would trigger the action
    """
    trigger_time_list = []
    manual_list = []
    for time_action, _, is_ext in zip(trace.actions, trace.pre_condition, trace.is_ext_list):
        time, action = time_action
        if action == target_action and is_ext:
            if is_ext:
                manual_list.append(time)
            else:
                trigger_time_list.append(time)

    orig_rule_trigger_time_list = []
    for orig_tap in orig_tap_list:
        _, rule_trigger_timing = getRealActionTimeAndRuleTriggerTime(trace, orig_tap, 
                                                                     target_action, False)
        orig_rule_trigger_time_list += rule_trigger_timing
    orig_rule_trigger_time_list = sorted(orig_rule_trigger_time_list)

    new_tap_cluster_trigger_time_list = []
    for tap_cluster in new_tap_cluster:
        new_tap = tap_cluster[0]
        _, rule_trigger_timing = getRealActionTimeAndRuleTriggerTime(trace, new_tap, 
                                                                     target_action, False, False)
        new_tap_cluster_trigger_time_list.append(rule_trigger_timing)
    
    return manual_list, trigger_time_list, orig_rule_trigger_time_list, new_tap_cluster_trigger_time_list


def calcScore(trace: Trace, target_action: str, tap: Tap, time_span: int=1200):
    target_action_timing, rule_trigger_timing = getRealActionTimeAndRuleTriggerTime(trace, tap, target_action)
    TP, FP, _ = getInfoFromTiming(rule_trigger_timing, target_action_timing, time_span)

    score = 0
    if TP != 0:
        score = TP * 1.0 / (TP + FP) * (1 + math.log(TP, 2))
    else:
        score = 0

    # TODO: very adhoc
    score = score * (2 + len(tap.condition)) if score < 0 else score / (2 + len(tap.condition))
    return score, TP, FP


def getTriggerTimeInTrace(trace: Trace, tap: Tap, check_enable=True):
    _, rule_trigger_timing = getRealActionTimeAndRuleTriggerTime(trace, tap, '', in_secs=False, check_enable=check_enable)
    return rule_trigger_timing


def calcMetaInfo(trace: Trace, target_action: str, tap: Tap, pre_time_span=900, post_time_span=120):
    target_action_timing, rule_trigger_timing = getRealActionTimeAndRuleTriggerTime(trace, tap, target_action, check_enable=False,  
                                                                                    revert_span=post_time_span)

    score = 0
    total_real = len(target_action_timing)
    total_recall = len(rule_trigger_timing)

    TP, FP, latency = getInfoFromTimingEnhanced(rule_trigger_timing, target_action_timing, pre_time_span, post_time_span)

    if TP != 0:
        score = TP * 1.0 / (TP + FP) * (1 + math.log(TP, 2))
    else:
        score = 0

    # TODO: very adhoc
    score = score * (2 + len(tap.condition)) if score < 0 else score / (2 + len(tap.condition))
    FN = total_real - TP
    if '#' in tap.trigger:
        longevity = int(tap.trigger.split('#')[0])
    elif '*' in tap.trigger:
        longevity = int(tap.trigger.split('*')[0])
    else:
        longevity = 0

    precision = TP*1.0/(TP+FP) if TP+FP != 0 else 0
    recall = TP*1.0/(TP+FN) if TP+FN != 0 else 0

    result = {
        'complexity': len(tap.condition),
        'precision': precision,
        'TP': TP,
        'FP': FP,
        'total_real': total_real,
        'total_recall': total_recall, 
        'recall': recall,
        'longevity': longevity,
        'latency': latency
    }
    # return len(tap.condition), precision, TP, recall, longevity, latency
    return result


def calcScoreEnhanced(trace: Trace, target_action: str, tap: Tap, pre_time_span=900, post_time_span=120):
    meta = calcMetaInfo(trace, target_action, tap, pre_time_span, post_time_span)
    # complexity, precision, TP, recall, longevity, latency = calcMetaInfo(trace, target_action, tap, time_span)
    complexity = meta['complexity']
    precision = meta['precision']
    TP = meta['TP']
    FP = meta['FP']
    recall = meta['recall']
    longevity = meta['longevity']
    latency = meta['latency']
    R = meta['total_real']

    score = 0
    score += 0.1852207702
    score += -0.05139802595 * complexity if complexity is not None else 0
    score += 0.2873206342 * precision if precision is not None else 0
    score += -0.002406847592 * TP if TP is not None else 0
    score += -0.04113189821 * recall if recall is not None else 0
    score += 0.0003873271773 * longevity if longevity is not None else 0
    score += -0.00001325811634 * latency if latency is not None else 0
    return score, TP, FP, R


def calcScoreDebug(system, time_event_cond_list, revert_list, tap_list):
    triggered_list = []
    for _, event, cond in time_event_cond_list:
        triggered = False
        for tap in tap_list:
            if system.tapConditionSatisfied(tap, cond) and checkEventAgainstTrigger(event, tap.trigger):
                triggered = True
                break
        triggered_list.append(triggered)
    TP = sum([(not tr) and rev for tr, rev in zip(triggered_list, revert_list)])
    FP = sum([(not tr) and (not rev) for tr, rev in zip(triggered_list, revert_list)])
    score = TP * 1.0 / (TP + FP)
    mask = [not tr for tr in triggered_list]
    return score, TP, FP, mask


def calcScoreTapDebug(tap_list, trace, mask, revert_list, time_event_cond_list, fn_episode_list, existing_time_points):
    # calculate the score for TapDebug
    # we assume that all rules in tap_list are for the target action
    # way to calc the score:
    # FP_fixed + FN_fixed - TP_cancelled - 0.25 * new_introduced

    # Calc FP_fixed and TP_cancelled
    FP_fixed = 0
    TP_cancelled = 0
    for ind in range(len(revert_list)):
        is_rev = revert_list[ind]
        is_triggered = mask[ind]
        if is_rev and not is_triggered:
            FP_fixed += 1
        if not is_rev and not is_triggered:
            TP_cancelled += 1
    
    # Calc FN_fixed
    FN_fixed = sum(mask[len(revert_list):])

    # Calc new_introduced
    fn_time_slots = sorted([(episode.start_time, episode.end_time) for episode in fn_episode_list])
    time_points = getTapListTriggerTime(trace, tap_list, for_vis=True)
    potential_new_time_points = set(time_points)
    curr_fn_slot = 0
    for t in time_points:
        while curr_fn_slot < len(fn_time_slots) and fn_time_slots[curr_fn_slot][1] < t:
            curr_fn_slot += 1
        if curr_fn_slot != len(fn_time_slots) and (fn_time_slots[curr_fn_slot][0] <= t and fn_time_slots[curr_fn_slot][1] >= t):
            if t in potential_new_time_points:
                potential_new_time_points.remove(t)

    new_time_points = {t for t in potential_new_time_points if t not in existing_time_points}
    new_time_points_inside_fn = {t for t in time_points if t not in existing_time_points and t not in new_time_points}
    new_introduced = len(new_time_points)
    meta = {
        'FP_fixed': FP_fixed,
        'FN_fixed': FN_fixed,
        'TP_cancelled': TP_cancelled,
        'new_introduced': new_introduced,
        'time_points': time_points,
        'time_points_outside_fn': sorted(list(new_time_points)),
        'time_points_inside_fn': sorted(list(new_time_points_inside_fn))
    }
    return FP_fixed + FN_fixed - TP_cancelled - 0.25 * new_introduced, meta


def analyzeTimeOrder(trace: Trace, target_action: str, tap: Tap, pre_time_span=900, post_time_span=120):
    target_action_timing, rule_trigger_timing = getRealActionTimeAndRuleTriggerTime(trace, tap, target_action, check_enable=False,  
                                                                                    revert_span=post_time_span)
    
    pre_n = 0
    post_n = 0
    for action_time in target_action_timing:
        rule_times_in_window = [rule_time for rule_time in rule_trigger_timing if action_time-pre_time_span <= rule_time < action_time+post_time_span]
        if rule_times_in_window:
            if rule_times_in_window[0] <= action_time:
                pre_n += 1
            else:
                post_n += 1
        else:
            pass
    
    return pre_n, post_n

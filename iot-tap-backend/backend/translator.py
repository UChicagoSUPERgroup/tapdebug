import backend.models as m

import json
import re
import webcolors


def trigger_to_clause(trigger,is_event):
    chan = {'id' : trigger.chan.id, 'name' : trigger.chan.name, 'icon' : trigger.chan.icon} if trigger.chan else {}
    if is_event:
        seconds_to_time = lambda s: {'hours': s // 3600, 'minutes': (s // 60) % 60, 'seconds': s % 60}
        c = {'channel' : chan,
            'device' : {'id' : trigger.dev.id,
                        'name' : trigger.dev.name},
            'capability' : {'id' : trigger.cap.id,
                            'name' : trigger.cap.name,
                            'label' : (trigger.cap.eventlabel if is_event else trigger.cap.statelabel),
                            'timelabel': trigger.cap.timeeventlabel},
            'text' : trigger.text,
            'id' : trigger.pos,
            'timeValue' : None if trigger.time_val is None or trigger.time_val == 0 else seconds_to_time(trigger.time_val)}
    else:
        c = {'channel' : chan,
            'device' : {'id' : trigger.dev.id,
                        'name' : trigger.dev.name},
            'capability' : {'id' : trigger.cap.id,
                            'name' : trigger.cap.name,
                            'label' : (trigger.cap.eventlabel if is_event else trigger.cap.statelabel), 
                            'timelabel': trigger.cap.timeeventlabel},
            'text' : trigger.text,
            'id' : trigger.pos}
    conds = m.Condition.objects.filter(trigger=trigger).order_by('id')
    if conds != []:
        c['parameters'] = []
        c['parameterVals'] = []

        for cond in conds:
            if cond.par.type == 'bin':
                values = [cond.par.binparam.tval, cond.par.binparam.fval]
            else:
                values = []
            val = json.loads(cond.val.replace('\'', '\"')) if cond.par.type in ('meta', 'duration') else cond.val
            c['parameters'].append({'id' : cond.par.id,
                                    'name' : cond.par.name,
                                    'type' : cond.par.type,
                                    'values': values})
            c['parameterVals'].append({'comparator' : cond.comp,
                                       'value' : val})
    return c

def action_to_clause(action):
    chan = {'id' : action.chan.id, 'name' : action.chan.name, 'icon' : action.chan.icon} if action.chan else {}
    c = {'channel' : chan,
         'device' : {'id' : action.dev.id,
                     'name' : action.dev.name},
         'capability' : {'id' : action.cap.id,
                         'name' : action.cap.name,
                         'label' : action.cap.commandlabel},
         'text' : action.text}
    action_conds = m.ActionCondition.objects.filter(action=action).order_by('id')
    if action_conds != []:
        c['parameters'] = []
        c['parameterVals'] = []

        for cond in action_conds:
            if cond.par.type == 'bin':
                values = [cond.par.binparam.tval, cond.par.binparam.fval]
            else:
                values = []
            val = json.loads(cond.val.replace('\'', '\"')) if cond.par.type in ('meta', 'duration') else cond.val
            c['parameters'].append({'id' : cond.par.id,
                                    'name' : cond.par.name,
                                    'type' : cond.par.type,
                                    'values': values})
            c['parameterVals'].append({'comparator' : '=',
                                       'value' : val})
    return c


def state_to_clause(state):
    chan = {'id' : state.chan.id, 'name' : state.chan.name, 'icon' : state.chan.icon} if state.chan else {}
    c = {'channel' : chan,
         'device' : {'id' : state.dev.id,
                     'name' : state.dev.name},
         'capability' : {'id' : state.cap.id,
                         'name' : state.cap.name,
                         'label' : state.cap.commandlabel},
         'text' : state.text}

    # pvs = m.ParVal.objects.filter(state=state).order_by('id')
    # if pvs != []:
    #     c['parameters'] = []
    #     c['parameterVals'] = []
    #
    #     for pv in pvs:
    #         c['parameters'].append({'id' : pv.par.id,
    #                                 'name' : pv.par.name,
    #                                 'type' : pv.par.type})
    #         c['parameterVals'].append({'comparator' : '=',
    #                                    'value' : pv.val})
    # escapeFunc = lambda x:re.sub(r'([\.\\\+\*\?\[\^\]\$\(\)\{\}\!\<\>\|\:\-])', r'\\\1', x)
    cap = m.Capability.objects.get(id=state.cap.id)
    par_list = m.Parameter.objects.filter(cap_id=cap.id)
    par_dict = dict()
    for par in par_list:
        values = []
        par_c = dict()
        par_c['id'] = par.id
        par_c['type'] = par.type
        par_c['name'] = par.name
        if par.type == 'bin':
            bin_par = m.BinParam.objects.get(id=par.id)
            par_c['value_list'] = [bin_par.fval, bin_par.tval]
            values = [bin_par.tval, bin_par.fval]
            t_template = r'\{%s/T\|(?P<value>[\w &\-]+)\}' % par.name
            f_template = r'\{%s/F\|(?P<value>[\w &\-]+)\}' % par.name
            t_val = re.search(t_template, cap.commandlabel)
            f_val = re.search(f_template, cap.commandlabel)
            if t_val and f_val:
                par_c['value_list_in_statement'] = [f_val.group('value'), t_val.group('value')]
            else:
                par_c['value_list_in_statement'] = par_c['value_list'] = [bin_par.fval, bin_par.tval]
        elif par.type == 'range':
            par_c['value_list'] = []
        elif par.type == 'set':
            par_c['value_list'] = [opt.value for opt in m.SetParamOpt.objects.filter(param_id=par.id)]
        elif par.type == 'color':
            par_c['value_list'] = [webcolors.CSS3_NAMES_TO_HEX.keys()]
        else:
            raise Exception('var type %s not supported' % par.type)
        par_c['values'] = values

        par_dict[par.name] = par_c

    template_text = re.sub(r'\{DEVICE\}', state.dev.name, cap.commandlabel)
    template_text = re.sub(r'\{(\w+)/(T|F)\|[\w &\-]+\}\{\1/(T|F)\|[\w &\-]+\}', r'(?P<\1>[\w &\-]+)', template_text)
    template_text = re.sub(r'\{(\w+)\}', r'(?P<\1>[\w &\-]+)', template_text)
    re_mat = re.match(template_text, state.text)

    for par, par_c in par_dict.items():
        par_dict[par_c['name']]['value'] = re_mat.group(par_c['name'])

    c['parameters'] = [{'type': par_c['type'], 'name': par_c['name'], 'id': par_c['id'], 'values': par_c['values']}
                       for par, par_c in sorted(par_dict.items())]
    c['parameterVals'] = list()
    for par, par_c in sorted(par_dict.items()):
        if par_c['type'] == 'bin':
            value = par_c['value_list'][par_c['value_list_in_statement'].index(par_c['value'])]
        else:
            value = par_c['value']
        c['parameterVals'].append({'comparator': '=', 'value': value})

    return c


def time_to_int(time):
    return time['seconds'] + time['minutes']*60 + time['hours']*3600

def int_to_time(secs):
    time = {}
    time['hours'] = secs // 3600
    time['minutes'] = (secs // 60) % 60
    time['seconds'] = secs % 60
    return time

def clause_to_trigger(clause):
    if 'channel' in clause and 'id' in clause['channel']:
        t = m.Trigger(chan=m.Channel.objects.get(id=clause['channel']['id']),
                    dev=m.Device.objects.get(id=clause['device']['id']),
                    cap=m.Capability.objects.get(id=clause['capability']['id']),
                    pos=clause['id'],
                    text=clause['text'])
        # NOTE: This is lagacy code. We don't handle timing here
    else:
        time_to_seconds = lambda c: c['hours'] * 3600 + c['minutes'] * 60 + c['seconds']
        t = m.Trigger(dev=m.Device.objects.get(id=clause['device']['id']),
                        cap=m.Capability.objects.get(id=clause['capability']['id']),
                    pos=clause['id'],
                    text=clause['text'],
                    time_val=time_to_seconds(clause['timeValue']) if clause['timeValue'] is not None else 0)
    t.save()

    try:
        pars = clause['parameters']
        vals = clause['parameterVals']
        for par,val in zip(pars,vals):
            cond = m.Condition(par=m.Parameter.objects.get(id=par['id']),
                               val=val['value'],
                               comp=val['comparator'],
                               trigger=t)
            cond.save()
    except KeyError:
        pass

    return t


def clause_to_action(clause):
    if 'channel' in clause and 'id' in clause['channel']:
        a = m.Action(chan=m.Channel.objects.get(id=clause['channel']['id']),
                     dev=m.Device.objects.get(id=clause['device']['id']),
                     cap=m.Capability.objects.get(id=clause['capability']['id']),
                     text=clause['text'])
    else:
        a = m.Action(dev=m.Device.objects.get(id=clause['device']['id']),
                     cap=m.Capability.objects.get(id=clause['capability']['id']),
                     text=clause['text'])
    a.save()

    try:
        pars = clause['parameters']
        vals = clause['parameterVals']
        for par,val in zip(pars,vals):
            cond = m.ActionCondition(par=m.Parameter.objects.get(id=par['id']),
                                     val=val['value'],
                                     action=a)
            cond.save()
    except KeyError:
        pass

    return a


def trigger_to_homeio_clause(trigger):
    clause = {}
    clause['dev'] = {
        'typ': trigger.dev.typ,
        'data_typ': trigger.dev.data_typ,
        'address': trigger.dev.address,
        'name': trigger.dev.name
    }

    cond = m.Condition.objects.get(trigger=trigger)

    clause['comp'] = cond.comp

    if cond.par.type == 'bin':
        clause['val'] = cond.val == cond.par.binparam.tval
    else:
        clause['val'] = cond.val

    clause['hold_t'] = trigger.time_val if trigger.time_val != 0 else None
    
    return clause



def action_to_homeio_clause(action):
    clause = {}
    clause['dev'] = {
        'typ': action.dev.typ,
        'data_typ': action.dev.data_typ,
        'address': action.dev.address,
        'name': action.dev.name
    }

    cond = m.ActionCondition.objects.get(action=action)

    clause['comp'] = '='
    if cond.par.type == 'bin':
        clause['val'] = cond.val == cond.par.binparam.tval
    else:
        clause['val'] = cond.val

    return clause


def homeio_info_to_dev_cap_param(typ, data_typ, address):
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

    typ, data_typ = typ_map[typ], datatype_map[data_typ]
    
    dev = m.Device.objects.get(typ=typ, data_typ=data_typ, address=address)
    cap = list(dev.caps.all())[0]
    param = m.Parameter.objects.get(cap=cap)
    return dev, cap, param


def homeio_val_to_val(hio_val, dev, param):
    if dev.data_typ == m.Device.BOOL:
        value = param.binparam.tval if hio_val else param.binparam.fval
        value_type = m.StateLog.STRING
    elif dev.data_typ == m.Device.FLOAT:
        value = float(hio_val)
        value_type = m.StateLog.NUMBER
    else:
        raise Exception('Unknown value type ' + dev.data_typ)
    return value, value_type

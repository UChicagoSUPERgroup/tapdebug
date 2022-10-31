import {
  OnInit, 
  Component,
  ViewChild,
  ViewContainerRef,
  ComponentFactoryResolver,
  ComponentRef,
  ComponentFactory
} from '@angular/core';
import { Router } from '@angular/router';
import { Location as _Location } from '@angular/common';
import { MatDialog } from '@angular/material';
import { CurrentruleComponent } from '../currentrule/currentrule.component';
import { VisbaseComponent } from '../vis/visbase/visbase.component';

import { UserDataService, Device, Location, Command, Rule, RuleUIRepresentation } from '../../user-data.service';
import { RsiService } from '../rsi.service';

@Component({
  selector: 'app-rsibasef',
  templateUrl: './rsibasef.component.html',
  styleUrls: ['./rsibasef.component.css']
})
export class RsibasefComponent implements OnInit {

  private currentDevice: Device;
  private currentCommand: Command;

  public showSpinner: boolean = true;

  // data representation for current rules
  public unparsedRules: Rule[];
  public RULES: RuleUIRepresentation[];

  // data representation for traces
  private traceLogs: any[];
  private devList: string[];
  private capList: string[];
  private targetId: number;

  // trace parsing helper
  private triggerReg: RegExp;


  // vis ref
  private refVis: ComponentRef<VisbaseComponent>;

  @ViewChild('viscontainer', { read: ViewContainerRef }) entry: ViewContainerRef;
  constructor(
    public userDataService: UserDataService, 
    public rsiService: RsiService,
    private resolver: ComponentFactoryResolver, private dialog: MatDialog, 
    private route: Router, 
    public _location: _Location) { }

  ngOnInit() {
    this.currentDevice = this.rsiService.currentDevice;
    this.currentCommand = this.rsiService.currentCommand;

    this.triggerReg = new RegExp("^(.*)_triggered\\[(.*)\\]$");

    // get data fetched from the previous page
    let data = this.rsiService.visData;
    
    this.unparsedRules = [...data["orig_rules"]];
    this.traceLogs = data["log_list"];
    this.devList = data["dev_list"];
    this.capList = data["cap_list"];
    this.targetId = data["target_id"];

    this.rsiService.cache_token = data["token"];

    for (let trace of this.traceLogs) {
      this.parseValueTypesForList(trace);
      this.addInterLineForList(['on', 'open', 'On', 'Open'], ['off', 'closed', 'Off', 'Closed'], 'solid_line_green', trace);
      this.addInterLineForList(['Motion', 'motion', 'active'], ['No Motion', 'no motion', 'inactive'], 'solid_line_coral', trace);
    }

    this.refVis = this.createVis(this.entry, this.traceLogs, this.devList, this.capList, this.targetId);

    this.RULES = this.userDataService.parseRules(this.unparsedRules);
    this.showSpinner = false;
  }

  public getCurrentCommandText() {
    return this.userDataService.getTextFromParVal(this.currentDevice, 
                                                  this.currentCommand.capability, 
                                                  [this.currentCommand.parameter], 
                                                  [{"value": this.currentCommand.value,
                                                    "comparator": "="}]);
  }

  public finishFeedback() {
    this.route.navigate(["/result"]);
  }

  openDialog() {
    const dialogRef = this.dialog.open(CurrentruleComponent, {
      data: {rules: this.RULES}
    });
  }

  createVis(entry, traceLogs, devList, capList, targetId) {
    entry.clear();
    const factory = this.resolver.resolveComponentFactory(VisbaseComponent);
    const componentRef = entry.createComponent(factory);
    componentRef.instance.traceLogs = traceLogs;
    componentRef.instance.maskList = traceLogs.map(x=>true);
    componentRef.instance.currentCluster = 0;
    componentRef.instance.mode = 1;
    componentRef.instance.devList = devList;
    componentRef.instance.capList = capList;
    componentRef.instance.targetId = targetId;
    componentRef.instance.tapSensorList = [[]];
    componentRef.instance.needComp = false;
    componentRef.instance.display = true;
    componentRef.instance.allowFeedback = true;

    return componentRef;
  }

  checkValue(typ_val, valueList) {
    const typ = typ_val[0];
    const val = typ_val[1];
    return valueList.includes(val) && !['origv', 'newtap'].includes(typ);
  }

  addInterLineForList(onValueList, offValueList, linetype, trace_log) {
    for (let dev_i = 0; dev_i < this.devList.length; dev_i++) {
      let current_value = -1;  // -1 for unknown, 0 for off, 1 for on
      let unknown_value = -1;
      for (let t_i = 0; t_i < trace_log.time_list.length; t_i++) {
        let old_event_list = trace_log.time_list[t_i].current_typ_vals[dev_i];
        let new_event_list = [];
        if (old_event_list.length && unknown_value == -1) {
          let first_event = old_event_list[0];
          if (this.checkValue(first_event, onValueList)) {
            unknown_value = 0;
            current_value = unknown_value;
          } else if (this.checkValue(first_event, offValueList)) {
            unknown_value = 1;
            current_value = unknown_value;
          } else {}
        }
        if (current_value == 1) {
          new_event_list.push([linetype, ''])
        }
        for (let event of old_event_list) {
          new_event_list.push(event);
          if (event[0] != 'orign') {
            if (this.checkValue(event, onValueList)) {
              current_value = 1;
              new_event_list.push([linetype, '']);
            } else if (this.checkValue(event, offValueList)) {
              current_value = 0;
            } else {}
          }
        }
        trace_log.time_list[t_i].current_typ_vals[dev_i] = new_event_list;
      }

      for (let t_i in trace_log.time_list) {
        let init = true;
        for (let l of trace_log.time_list[t_i].current_typ_vals[dev_i]) {
          if (l[0] != 'origv' || l[0] != 'newtap') {
            init = false;
            break;
          }
        }
        if (init) {
          if (unknown_value == 1) {
            trace_log.time_list[t_i].current_typ_vals[dev_i].splice(0, 0, [linetype, ''])
            trace_log.time_list[t_i].current_typ_vals[dev_i].push([linetype, '']);
          }
        } else {
          break;
        }
      }
    }
  }

  getOrigTypeValue(v) {
    if(['on', 'open', 'On', 'Open'].includes(v)) {
      return ['on', v];
    } else if(['off', 'closed', 'Off', 'Closed'].includes(v)) {
      return ['off', v];
    } else if(['motion', 'no motion', 'active', 'inactive', 'Motion', 'No Motion'].includes(v)) {
      return ['motion', v];
    } else if(['triggered'].includes(v)) {
      return ['blue_dot', ''];
    } else if(['solid_line_green'].includes(v)) {
      return ['solid_line_green', ''];
    } else if(['solid_line_coral'].includes(v)) {
      return ['solid_line_coral', ''];
    } else {
      return ['plain', v];
    }
  }

  parseValueTypesForList(trace_log) {
    for (let status of trace_log.time_list) {
      let current_typ_vals = status.current_values.map(values => {
        let t_v_list = [];
        for (let value of values) {
          let trigger = this.triggerReg.test(value);
          if (trigger) {
            let match = this.triggerReg.exec(value);
            let tap = match[1];
            let val = match[2];
            if (tap == 'orig') {
              let typ_val = this.getOrigTypeValue(val);
              typ_val[0] = 'orig';
              t_v_list.push(typ_val);
            } else if (tap == 'orign') {
              let typ_val = this.getOrigTypeValue(val);
              typ_val[0] = 'orign';
              t_v_list.push(typ_val);
            } else if (tap == 'origv') {
              t_v_list.push(['origv', val]);
            } else if (tap == 'del') {
              t_v_list.push(['del', val]);
            }
          } else {
            t_v_list.push(this.getOrigTypeValue(value));
          }
        }
        return t_v_list;
        
      });
      status.current_typ_vals = current_typ_vals;
    }
  }

  backToOptions() {
    this.route.navigate(['/synthesize/zonesel', { dataFetched: true }]);
  }
}

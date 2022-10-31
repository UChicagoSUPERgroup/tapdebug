import { Component, OnInit, ViewChild, ViewContainerRef, ComponentFactoryResolver, ComponentRef } from '@angular/core';
import { Router } from '@angular/router';
import { UserDataService } from '../../user-data.service';

import { VisbaseComponent as VisbaseDrawingComponent } from '../../rsi/vis/visbase/visbase.component';

@Component({
  selector: 'app-visbase',
  templateUrl: './visbase.component.html',
  styleUrls: ['./visbase.component.css']
})
export class VisbaseComponent implements OnInit {

  public showSpinner: boolean = true;
  public devList: string[];
  public capList: string[];
  private triggerReg: RegExp;
  public traceLog: any;
  private targetId: number = 0;

  @ViewChild('vis', { read: ViewContainerRef }) entry: ViewContainerRef;
  private refVis: ComponentRef<VisbaseDrawingComponent>;

  constructor(private userDataService: UserDataService, private route: Router, 
              private resolver: ComponentFactoryResolver) { }

  ngOnInit(): void {
    this.triggerReg = new RegExp("^(.*)_triggered\\[(.*)\\]$");
    let self = this;
    this.userDataService.getLocationToken().subscribe(u_data => {
      // this.userDataService.fetchLogManual(
      //   this.userDataService.current_loc, this.userDataService.visEntities, 
      //   this.userDataService.startDatetime, this.userDataService.endDatetime
      // ).subscribe(data => {
      //   // initialize selection bits
      //   this.devList = data["dev_list"];
      //   this.capList = data["cap_list"];
      //   this.traceLog = data["log"];
      //   this.parseValueTypesForList(this.traceLog);
      //   let unrelated_devices_index = Array.from(Array(this.devList.length).keys());
      //   unrelated_devices_index.splice(unrelated_devices_index.indexOf(this.targetId), 1);
      //   this.addInterLineForList(['on', 'open', 'On', 'Open'], ['off', 'closed', 'Off', 'Closed'], 'solid_line_green', this.traceLog);
      //   this.addInterLineForList(['Motion', 'motion', 'active'], ['No Motion', 'no motion', 'inactive'], 'solid_line_coral', this.traceLog);

      //   this.refVis = this.createVis(this.entry, this.traceLog, this.devList, this.capList, this.targetId);
      //   this.showSpinner = false;
      // });
    });
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
          if (this.checkValue(event, onValueList)) {
            current_value = 1;
            new_event_list.push([linetype, '']);
          } else if (this.checkValue(event, offValueList)) {
            current_value = 0;
          } else {}
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

  createVis(entry, traceLog, devList, capList, targetId) {
    entry.clear();
    const factory = this.resolver.resolveComponentFactory(VisbaseDrawingComponent);
    const componentRef = entry.createComponent(factory);
    componentRef.instance.traceLogs = [traceLog];
    componentRef.instance.maskList = [true];
    componentRef.instance.currentCluster = 0;
    componentRef.instance.mode = 1;
    componentRef.instance.devList = devList;
    componentRef.instance.capList = capList;
    componentRef.instance.targetId = targetId;
    componentRef.instance.tapSensorList = [[]];
    componentRef.instance.needComp = false;
    componentRef.instance.display = true;

    return componentRef;
  }
  goToDashboard() {
    this.route.navigate(["admin/"]);
  }
}

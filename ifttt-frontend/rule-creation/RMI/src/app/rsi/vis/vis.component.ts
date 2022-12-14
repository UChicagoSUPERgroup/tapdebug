import { Component, OnInit, Input, ViewChild, ViewContainerRef, ComponentFactoryResolver, ComponentRef } from '@angular/core';
import { MatDialog } from '@angular/material';
import { UserDataService } from '../../user-data.service';
import { StatusComponent } from './status/status.component';
import { LegendComponent } from './legend/legend.component';
import { VisbaseComponent } from './visbase/visbase.component';

export interface PatchMeta {
  FP_fixed: number,
  FN_fixed: number,
  TP_cancelled: number,
  new_introduced: number
}

@Component({
  selector: 'app-vis',
  templateUrl: './vis.component.html',
  styleUrls: ['./vis.component.css']
})
export class VisComponent implements OnInit {
  @Input() traceLogsFN: any[] = [];
  @Input() traceLogsTEC: any[] = [];
  @Input() traceLogsNI: any[] = [];
  @Input() maskFN: boolean[] = [];
  @Input() maskTEC: number[] = [];
  @Input() maskNI: boolean[] = [];
  @Input() currentCluster: number;
  @Input() mode: boolean;  // 0: feedback from trace; 1: feedback from interface
  @Input() devList: string[] = [];
  @Input() capList: string[] = [];
  @Input() tapLogsShownPositive: any[] = [];
  @Input() tapLogsShownNegative: any[] = [];
  @Input() targetId: number = 0;
  @Input() tapSensorList: any[] = [];
  @Input() patchMeta: PatchMeta = {FP_fixed: 0, FN_fixed: 0, TP_cancelled: 0, new_introduced: 0};
  @Input() currentCommandText: string = "";
  @Input() nRevert: number = 0;
  
  public unrelated_devices_index: any[];
  private triggerReg: RegExp;
  private nCap: number = 10;
  private nMaxTraces: number = 200;
  public showFPFixed: boolean = false;
  public showFNFixed: boolean = false;
  public showTPCancelled: boolean = false;
  public showNewIntroduced: boolean = false;

  @ViewChild('visfpfixed', { read: ViewContainerRef }) entryFPFixed: ViewContainerRef;
  @ViewChild('visfnfixed', { read: ViewContainerRef }) entryFNFixed: ViewContainerRef;
  @ViewChild('vistpcancelled', { read: ViewContainerRef }) entryTPCancelled: ViewContainerRef;
  @ViewChild('visnewintroduced', { read: ViewContainerRef }) entryNewIntroduced: ViewContainerRef;

  private refFPFixed: ComponentRef<VisbaseComponent>;
  private refFNFixed: ComponentRef<VisbaseComponent>;
  private refTPCancelled: ComponentRef<VisbaseComponent>;
  private refNewIntroduced: ComponentRef<VisbaseComponent>;

  constructor(public userDataService: UserDataService,
    private dialog: MatDialog, private resolver: ComponentFactoryResolver) {  }

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
            } else if (tap == 'deln') {
              t_v_list.push(['deln', val]);
            } else {
              let tap_id = +tap;
              if (tap_id == this.currentCluster) {
                t_v_list.push(['newtap', val]);
              }
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

  parseValueTypes() {
    // parse value types for all four trace logs
    for (let trace_log of this.traceLogsFN) {
      this.parseValueTypesForList(trace_log)
    }
    for (let trace_log of this.traceLogsTEC) {
      this.parseValueTypesForList(trace_log)
    }
    for (let trace_log of this.traceLogsNI) {
      this.parseValueTypesForList(trace_log)
    }
  }

  checkValue(typ_val, valueList) {
    const typ = typ_val[0];
    const val = typ_val[1];
    return valueList.includes(val) && !['origv', 'newtap'].includes(typ);
  }

  addInterLineForList(onValueList, offValueList, linetype, traceLogs) {
    for (let trace_log of traceLogs) {
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
            if (event[0] != 'deln') {
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
  }

  addInterLine(onValueList, offValueList, linetype) {
    this.addInterLineForList(onValueList, offValueList, linetype, this.traceLogsFN);
    this.addInterLineForList(onValueList, offValueList, linetype, this.traceLogsTEC);
    this.addInterLineForList(onValueList, offValueList, linetype, this.traceLogsNI);
  }

  ngOnInit() {
    // if we have too many traces, trim them
    if (this.traceLogsFN.length > this.nMaxTraces) {
      this.traceLogsFN = this.traceLogsFN.slice(0, this.nMaxTraces);
      this.maskFN = this.maskFN.slice(0, this.nMaxTraces);
    }
    if (this.traceLogsTEC.length > this.nMaxTraces) {
      this.traceLogsTEC = this.traceLogsTEC.slice(0, this.nMaxTraces);
      this.maskTEC = this.maskTEC.slice(0, this.nMaxTraces);
    }
    if (this.traceLogsNI.length > this.nMaxTraces) {
      this.traceLogsNI = this.traceLogsNI.slice(0, this.nMaxTraces);
      this.maskNI = this.maskNI.slice(0, this.nMaxTraces);
    }

    this.triggerReg = new RegExp("^(.*)_triggered\\[(.*)\\]$");
    this.parseValueTypes();
    let unrelated_devices_index = Array.from(Array(this.devList.length).keys());
    unrelated_devices_index.splice(unrelated_devices_index.indexOf(this.targetId), 1);
    for (let s_i of this.tapSensorList[this.currentCluster]) {
      unrelated_devices_index.splice(unrelated_devices_index.indexOf(s_i), 1);
    }
    let n_cap = this.nCap - 1 - this.tapSensorList[this.currentCluster].length;
    n_cap = n_cap > 0 ? n_cap : 0;
    this.unrelated_devices_index = unrelated_devices_index.slice(0, n_cap);
    this.addInterLine(['on', 'open', 'On', 'Open'], ['off', 'closed', 'Off', 'Closed'], 'solid_line_green');
    this.addInterLine(['Motion', 'motion', 'active'], ['No Motion', 'no motion', 'inactive'], 'solid_line_coral');

    // TODO: probably we can get rid of masks
    this.refFPFixed = this.createVis(this.entryFPFixed, this.traceLogsTEC, this.maskTEC.map(x => x == 1), 
                   this.currentCluster, true, this.devList, this.capList, this.targetId, this.tapSensorList);
    this.refFNFixed = this.createVis(this.entryFNFixed, this.traceLogsFN, this.maskFN, 
                   this.currentCluster, true, this.devList, this.capList, this.targetId, this.tapSensorList);
    this.refTPCancelled = this.createVis(this.entryTPCancelled, this.traceLogsTEC, this.maskTEC.map(x => x == 2), 
                    this.currentCluster, true, this.devList, this.capList, this.targetId, this.tapSensorList);
    this.refNewIntroduced = this.createVis(this.entryNewIntroduced, this.traceLogsNI, this.maskNI, 
                    this.currentCluster, true, this.devList, this.capList, this.targetId, this.tapSensorList);
  }

  getDeviceImg(d) {
    let path = "assets/";
    if (d.includes('Fan') || d.includes('fan')) {
      return path + 'fan.png';
    } else if (d.includes('Button') || d.includes('button')) {
      return path + 'button.jpg';
    } else if (d.includes('Aeotec') || d.includes('multisensor') || d.includes('Multisensor') || d.includes('MultiSensor')) {
      return path + 'aeotec.jpg';
    } else if (d.includes('Lightstrip') || d.includes('lightstrip')) {
      return path + 'hue_lightstrip.jpg';
    } else if (d.includes('Weather') || d.includes('weather')) {
      return path + 'weather.png';
    } else if (d.includes('Motion') || d.includes('motion')) {
      return path + 'motionsensor.jpg';
    } else if (d.includes('Multipurpose') || d.includes('Multipurpose') || d.includes('Door') || d.includes('door')) {
      return path + 'multipurpose.jpg';
    } else if (d.includes('Humidifier')) {
      return path + 'Humidifier.jpeg';
    } else if (d.includes('Lamp') || d.includes('lamp')) {
      return path + 'Lamp.jpeg';
    } else if (d.includes('Kettle') || d.includes('kettle')) {
      return path + 'Kettle.jpg';
    } else if (d.includes('Outlet') || d.includes('outlet')) {
      return path + 'outlet.jpg';
    } else {
      return '';
    }
  }

  getDateTimeFormat(date) {
    let date_time = date.split(' ');
    let typ = false;
    if (['0', '5'].includes(date_time[1].charAt(date_time[1].length-1))) {
      typ = true;
    }
    return [typ, date_time[0] + 'T' + date_time[1] + '+00:00'];
  }

  isUnrelated(trace, d_i) : boolean {
    return d_i != trace.target_action_id && !trace.rule_sensor_list[this.currentCluster].includes(d_i);
  }

  getLastInMask(mask: boolean[]) {
    let len = mask.length;
    for (let i=len-1; i>=0; i--) {
      if (mask[i]) {
        return i;
      }
    }
    return -1;
  }

  openLegend() {
    const dialogRef = this.dialog.open(LegendComponent);
  }

  createVis(entry, traceLogs, maskList, currentCluster, mode, 
            devList, capList, targetId, tapSensorList) {
    entry.clear();
    const factory = this.resolver.resolveComponentFactory(VisbaseComponent);
    const componentRef = entry.createComponent(factory);
    componentRef.instance.traceLogs = traceLogs;
    componentRef.instance.maskList = maskList;
    componentRef.instance.currentCluster = currentCluster;
    componentRef.instance.mode = mode ? 1: 0;
    componentRef.instance.devList = devList;
    componentRef.instance.capList = capList;
    componentRef.instance.targetId = targetId;
    componentRef.instance.tapSensorList = tapSensorList;
    componentRef.instance.needComp = false;

    return componentRef;
  }

  flipFPFixed() {
    this.showFPFixed = !this.showFPFixed;
    this.refFPFixed.instance.display = this.showFPFixed;
  }

  flipFNFixed() {
    this.showFNFixed = !this.showFNFixed;
    this.refFNFixed.instance.display = this.showFNFixed;
  }

  flipTPCancelled() {
    this.showTPCancelled = !this.showTPCancelled;
    this.refTPCancelled.instance.display = this.showTPCancelled;
  }

  flipNewIntroduced() {
    this.showNewIntroduced = !this.showNewIntroduced;
    this.refNewIntroduced.instance.display = this.showNewIntroduced;
  }
}
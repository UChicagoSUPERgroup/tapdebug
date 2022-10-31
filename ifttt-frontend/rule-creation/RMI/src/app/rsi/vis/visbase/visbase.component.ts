import { Component, OnInit, Input, ViewChild, ElementRef } from '@angular/core';
import { MatDialog } from '@angular/material';

import { FeedbackComponent } from '../feedback/feedback.component';
import { RsiService } from '../../rsi.service';
import { UserDataService } from '../../../user-data.service';

@Component({
  selector: 'app-visbase',
  templateUrl: './visbase.component.html',
  styleUrls: ['./visbase.component.css']
})
export class VisbaseComponent implements OnInit {

  @Input() traceLogs: any[] = [];
  @Input() maskList: boolean[] = [];
  @Input() currentCluster: number;
  @Input() mode: number;  // False: suggest new rules, True: fix existing ones
  @Input() devList: string[];
  @Input() capList: string[];
  @Input() targetId: number;
  @Input() tapSensorList: any[];
  @Input() needComp: boolean;
  @Input() display: boolean = false;
  @Input() allowFeedback: boolean = false;

  // the feedback tag showing users what would be added
  @ViewChild('feedbackevent') feedbackEvent: ElementRef;

  // enhanced device list that highlights location of the device
  public enhancedDevList: string[][];

  // For each log in the traceLogs, maintain a list of 
  // the height needed for each entry (List[List[number]]).
  public entryHeights: any[] = [];

  public unrelated_devices_index: any[];
  private triggerReg: RegExp;
  private nCap: number = 10;
  
  public showFeedback: boolean = false;
  public feedbackTop: any;
  public feedbackLeft: any;
  public targetValue: string;

  constructor(
    private dialog: MatDialog,
    public rsiService: RsiService,
    private userDataService: UserDataService
  ) { }

  ngOnInit() {
    if (this.needComp) {
      this.triggerReg = new RegExp("^(.*)_triggered\\[(.*)\\]$");
      this.parseValueTypes();
    }

    this.enhancedDevList = this.devList.map(x => this.userDataService.parseLocationForRuleDescription(x));
    
    let unrelated_devices_index = Array.from(Array(this.devList.length).keys());
    unrelated_devices_index.splice(unrelated_devices_index.indexOf(this.targetId), 1);
    for (let s_i of this.tapSensorList[this.currentCluster]) {
      unrelated_devices_index.splice(unrelated_devices_index.indexOf(s_i), 1);
    }
    let n_cap = this.nCap - 1 - this.tapSensorList[this.currentCluster].length;
    n_cap = n_cap > 0 ? n_cap : 0;
    this.unrelated_devices_index = unrelated_devices_index.slice(0, n_cap);
    if (this.needComp) {
      this.addInterLine(['on', 'open', 'On', 'Open'], ['off', 'closed', 'Off', 'Closed'], 'solid_line_green');
      this.addInterLine(['Motion', 'motion', 'active'], ['No Motion', 'no motion', 'inactive'], 'solid_line_coral');
    }

    // initialize the value shown in the feedback visual hint
    this.targetValue = this.rsiService.currentCommand.value;

    this.calculateHeights();
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
  }

  addInterLine(onValueList, offValueList, linetype) {
    this.addInterLineForList(onValueList, offValueList, linetype, this.traceLogs);
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

  parseValueTypes() {
    for (let trace_log of this.traceLogs) {
      this.parseValueTypesForList(trace_log);
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

  getDeviceImg(d) {
    let path = "assets/devices/";
    if (d.includes('Motion Detector')) {
      return path + 'motionsensor.PNG';
    } else if (d.includes('Roller Shade')) {
      return path + 'rollershade.PNG';
    } else if (d.includes('Door Detector')) {
      return path + 'doordetector.PNG';
    } else if (d.includes('Entrance Gate')) {
      return path + 'entrancegate.PNG';
    } else if (d.includes('Brightness Sensor')) {
      return path + 'brightnesssensor.PNG';
    } else if (d.includes('Infrared')) {
      return path + 'infraredsensor.PNG';
    } else if (d.includes('Garage Door')) {
      return path + 'garagedoor.PNG';
    } else if (d.includes('Light')) {
      return path + 'light.PNG';
    } else if (d.includes('Smoke Detector')) {
      return path + 'smokedetector.PNG';
    } else if (d.includes('Temperature')) {
      return path + 'thermostat.PNG';
    } else if (d.includes('Alarm Key Pad')) {
      return path + 'alarmkeypad.PNG';
    } else {
      return '';
    }
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

  getDateTimeFormat(date) {
    let date_time = date.split(' ');
    let typ = false;
    if (['0', '5'].includes(date_time[1].charAt(date_time[1].length-1))) {
      typ = true;
    }
    return [typ, date_time[0] + 'T' + date_time[1] + '+00:00'];
  }

  feedbackFN(event: MouseEvent, trace_index: number, entry_index: number) {
    if (this.rsiService.modification == 1) {
      let target: HTMLTableDataCellElement = null;  // event.target as HTMLTableDataCellElement;
      let parent: HTMLTableElement = null;  // target.offsetParent as HTMLTableElement;

      for (let entry of event.composedPath()) {
        let e = entry as HTMLElement;
        if (e.className.includes("target_column_feedback")) {
          target = e as HTMLTableDataCellElement;
          parent = e.offsetParent as HTMLTableElement;
          break;
        }
      }

      if (target == null || parent == null) {
        console.error("target_column_feedback unfound");
      }

      let seconds = Math.floor(60 * (event.pageY - parent.offsetTop - target.offsetTop) / target.offsetHeight);
      seconds = seconds >= 0 ? seconds : 0;
      seconds = seconds < 60 ? seconds : 59;
      let time_str = this.traceLogs[trace_index].time_list[entry_index].time + ":" + seconds;

      let fbTop = Math.floor(parent.offsetTop + target.offsetTop + target.offsetHeight/2 - 11) + "px";
      let fbLeft = Math.floor(parent.offsetLeft + target.offsetLeft + target.offsetWidth/2 - 25) + "px";
      // this.rsiService.currentFeedbackTime = time_str;
      // this.rsiService.currentMode = true;

      this.rsiService.addFNFeedback(time_str, fbTop, fbLeft);

      // this.dialog.open(FeedbackComponent);
    }
    else{
      console.log("You chose option 2 or 3 not 1!");
    }
  }

  calculateEntryHeight(typ_vals) {
    let height = 0;
    for (let typ_val of typ_vals) {
      let typ = typ_val[0];
      if (['motion', 'blue_dot'].includes(typ)) {
        height += 8;
      } else if (['plain', 'on', 'off', 'orig', 'orign', 'del', 'deln'].includes(typ)) {
        height += 14;
      }
    }
    return height;
  }

  calculateHeights() {
    this.entryHeights = [];
    for (let trace of this.traceLogs) {
      let heightList = [];
      for (let status of trace.time_list) {
        let currentHeight = 35;
        for (let typ_vals of status.current_typ_vals) {
          let height = this.calculateEntryHeight(typ_vals);
          if (height > currentHeight) {
            currentHeight = height;
          }
        }
        heightList.push(currentHeight);
      }
      this.entryHeights.push(heightList);
    }
  }

  // moveInFeedbackZone(event: MouseEvent) {
  //   if (this.rsiService.modification != 1)
  //     return;

  //   let target: HTMLTableDataCellElement = null;  // event.target as HTMLTableDataCellElement;
  //   let parent: HTMLTableElement = null;  // target.offsetParent as HTMLTableElement;

  //   for (let entry of event.composedPath()) {
  //     let e = entry as HTMLElement;
  //     if (e.className.includes("target_column_feedback")) {
  //       target = e as HTMLTableDataCellElement;
  //       parent = e.offsetParent as HTMLTableElement;
  //       break;
  //     }
  //   }

  //   if (target == null || parent == null) {
  //     console.error("target_column_feedback unfound");
  //   }

  //   this.showFeedback = true;
  //   this.feedbackTop = Math.floor(parent.offsetTop + target.offsetTop + target.offsetHeight/2 - 5) + "px";
  //   this.feedbackLeft = Math.floor(parent.offsetLeft + target.offsetLeft + target.offsetWidth/2 - 25) + "px";
  // }

  // moveOutFeedbackZone() {
  //   this.showFeedback = false;
  // }

  // @HostListener('document:mousemove', ['$event'])
  // onMousemove($event) {
  //   this.top = ($event.pageY)+"px";
  //   this.left = ($event.pageX)+"px";
  // }
}

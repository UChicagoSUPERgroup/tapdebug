import { Component, OnInit, Input } from '@angular/core';
import { MatDialog } from '@angular/material';

import { FeedbackComponent } from '../feedback/feedback.component';
import { RsiService } from '../../rsi.service';

@Component({
  selector: 'vis-status',
  templateUrl: './status.component.html',
  styleUrls: ['./status.component.css']
})
export class StatusComponent implements OnInit {
  @Input() logId: number = 0;
  @Input() timeStr: string = "";
  @Input() allowFeedback: boolean = false;
  @Input() value: any;
  @Input() mode: number;  // 0: new 1: fix 2:revert
  @Input() currentCluster: number;
  @Input() height: number = 35;
  public modification: number;

  constructor(private rsiService: RsiService, private dialog: MatDialog) { }

  ngOnInit() {
  }

  // getOrigTypeValue(v) {
  //   if(['on', 'open', 'On', 'Open'].includes(v)) {
  //     return ['triangle-on', ''];
  //   } else if(['off', 'closed', 'Off', 'Closed'].includes(v)) {
  //     return ['triangle-off', ''];
  //   } else if(['motion', 'no motion', 'active', 'inactive', 'Motion', 'No Motion'].includes(v)) {
  //     return ['coral_dot', ''];
  //   } else if(['triggered'].includes(v)) {
  //     return ['blue_dot', ''];
  //   } else if(['solid_line_green'].includes(v)) {
  //     return ['solid_line_green', ''];
  //   } else if(['solid_line_coral'].includes(v)) {
  //     return ['solid_line_coral', ''];
  //   } else {
  //     return ['plain', v];
  //   }
  // }

  getValueType(value) {
    let total_height = this.height;

    // remove fixed items' height from total height
    let num_line = 0;
    for (let typ_val of value) {
      let typ = typ_val[0];
      if (['motion', 'blue_dot'].includes(typ)) {
        total_height -= 8;
      } else if (['plain', 'on', 'off', 'orig', 'orign', 'del', 'deln'].includes(typ)) {
        total_height -= 14;
      } else if (['solid_line_coral', 'line', 'solid_line_green'].includes(typ)) {
        num_line += 1;
      }
    }
    let line_height = total_height > 0? total_height / num_line: 0;

    let result = [];
    for (let index in value) {
      let typ = value[index][0];
      let val = value[index][1];
      let height = '0px';
      if (['solid_line_coral', 'line', 'solid_line_green'].includes(typ)) {
        height = String(line_height) + 'px';
      } else if (['motion', 'blue_dot'].includes(typ)) {
        height = String(8) + 'px';
      } else if (['plain', 'on', 'off', 'newtap', 'orig', 'orign', 'origv', 'del', 'deln'].includes(typ)) {
        height = String(14) + 'px';
      }
      result.push([typ, val, height])
    }
    return result;

  }

  feedbackFP(event: MouseEvent, logId: number, timeStr: string, entryId: number) {
    event.stopPropagation();
    this.modification = this.rsiService.modification;

    if (this.modification == 2 || this.modification == 3) {
      // we first need to get the real entryId
      // do not count entries with type "solid_line_coral", "line", "solid_line_green", etc.
      let realEntryId = 0;
      for (let ii = 0; ii < entryId; ii++) {
        let typ = this.value[ii][0];
        if (!['solid_line_coral', 'line', 'solid_line_green'].includes(typ)) {
          realEntryId++;
        }
      }
      let key = logId + "," + timeStr + "," + entryId;
      if (this.rsiService.currentFPFeedbacks.has(key))
        this.rsiService.removeFPFeedback(logId, timeStr, realEntryId, entryId);
      else
        this.rsiService.addFPFeedback(logId, timeStr, realEntryId, entryId);
      // this.rsiService.currentLogId = logId;
      // this.rsiService.currentTimeStr = timeStr;
      // this.rsiService.currentEntryId = realEntryId;
      // this.rsiService.currentMode = false;
      // this.dialog.open(FeedbackComponent);
    }
    else {
      console.log("You chose option 1, not 2 or 3!");
    }
  }

  checkFP(logId: number, timeStr: string, entryId: number) {
    let key = logId + "," + timeStr + "," + entryId;
    return this.rsiService.currentFPFeedbacks.has(key);
  }
}

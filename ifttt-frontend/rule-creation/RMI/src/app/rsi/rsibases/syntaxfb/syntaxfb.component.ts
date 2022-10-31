import { Component, OnInit } from '@angular/core';
import { MatDialogRef } from '@angular/material';

import { UserDataService, Device, Command } from '../../../user-data.service';
import { RsiService } from '../../rsi.service';

@Component({
  selector: 'app-syntaxfb',
  templateUrl: './syntaxfb.component.html',
  styleUrls: ['./syntaxfb.component.css']
})
export class SyntaxfbComponent implements OnInit {

  constructor(
    public userDataService: UserDataService,
    public rsiService: RsiService,
    private _dialogRef: MatDialogRef<SyntaxfbComponent>
  ) { }

  ngOnInit() {
  }

  finish(valueOnly: boolean=false) {
    if (this.rsiService.currentSyntaxMode == 0) {
      
      if (this.rsiService.currentConditionId < 0) {
        // change a trigger
        let syntaxMode = valueOnly ? 'change-trig-param' : 'change-trig';
        this.rsiService.currentSyntaxFeedbacks.push({
          'rule_id': this.rsiService.currentRuleId,
          'cond_id': this.rsiService.currentConditionId,
          'mode': syntaxMode
        });
        let tup = this.rsiService.tupleToStr(this.rsiService.currentRuleId, 0);
        if (!this.rsiService.syntaxFbDict.has(tup))
          this.rsiService.syntaxFbDict.add(tup);
      } else {
        // change a condition
        let syntaxMode = valueOnly ? 'change-cond-param' : 'change-cond';
        this.rsiService.currentSyntaxFeedbacks.push({
          'rule_id': this.rsiService.currentRuleId,
          'cond_id': this.rsiService.currentConditionId,
          'mode': syntaxMode
        });
        let tup = this.rsiService.tupleToStr(this.rsiService.currentRuleId, this.rsiService.currentConditionId+1);
        if (!this.rsiService.syntaxFbDict.has(tup))
          this.rsiService.syntaxFbDict.add(tup);
      }
    } else if (this.rsiService.currentSyntaxMode == 1) {
      // add a condition
      this.rsiService.currentSyntaxFeedbacks.push({
        'rule_id': this.rsiService.currentRuleId,
        'mode': 'add-cond'
      });
      let tup = this.rsiService.tupleToStr(this.rsiService.currentRuleId, -1);
      if (!this.rsiService.syntaxFbDict.has(tup))
          this.rsiService.syntaxFbDict.add(tup);
    } else if (this.rsiService.currentSyntaxMode == 2) {
      // add a new rule
      this.rsiService.currentSyntaxFeedbacks.push({
        'mode': 'add-rule'
      });
      let tup = this.rsiService.tupleToStr(-1, -1);
      if (!this.rsiService.syntaxFbDict.has(tup))
          this.rsiService.syntaxFbDict.add(tup);
    }
    this._dialogRef.close();
  }

  dismiss() {
    this._dialogRef.close();
  }
}

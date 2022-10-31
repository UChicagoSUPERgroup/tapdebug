import { Component, OnInit } from '@angular/core';
import { MatDialogRef } from '@angular/material';
import { Router, ActivatedRoute } from '@angular/router';
import { UserDataService, Device, Command } from '../../../user-data.service';
import { RsiService } from '../../rsi.service';

@Component({
  selector: 'app-feedback',
  templateUrl: './feedback.component.html',
  styleUrls: ['./feedback.component.css']
})
export class FeedbackComponent implements OnInit {

  private currentDevice: Device;
  private currentCommand: Command;
  public shouldHappenText: string;

  public currentMode: boolean;
  public modification: number;


  constructor(
    public userDataService: UserDataService,
    public rsiService: RsiService,
    private route: Router,
    private router: ActivatedRoute,
    private _dialogRef: MatDialogRef<FeedbackComponent>
  ) { }

  ngOnInit() {
    this.currentDevice = this.rsiService.currentDevice;
    this.currentCommand = this.rsiService.currentCommand;
    this.currentMode = this.rsiService.currentMode;
  
    this.shouldHappenText = this.userDataService.getTextFromParVal(
      this.currentDevice, 
      this.currentCommand.capability, 
      [this.currentCommand.parameter], 
      [{"value": this.currentCommand.value,
        "comparator": "="}]
    );
  }

  save() {
    // if (this.currentMode) {
    //   console.log("path: 1");
    //   this.rsiService.currentFNFeedbacks.push({
    //     'time': this.rsiService.currentFeedbackTime,
    //     'device': this.currentDevice,
    //     'command': this.currentCommand
    //   });
    //   console.log("FNlength: ", this.rsiService.currentFNFeedbacks.length);
    //   this.route.navigate(["/choices"], {skipLocationChange: true });

    // } else {
    //   console.log("path: 2");
    //   this.rsiService.currentFPFeedbacks.push({
    //     'log_id': this.rsiService.currentLogId,
    //     'time_str': this.rsiService.currentTimeStr,
    //     'entry_id': this.rsiService.currentEntryId
    //   });
    //   console.log("FPlength: ", this.rsiService.currentFPFeedbacks.length);
    //   this.route.navigate(["/choices"], {skipLocationChange: true });
    // }
    
    this._dialogRef.close();
  }

  dismiss() {
    this._dialogRef.close();
  }

  readModificationVariable(){
    this.modification = this.rsiService.modification;
    return this.modification;
  }
}

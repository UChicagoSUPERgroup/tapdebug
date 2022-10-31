import { Injectable, Inject, LOCALE_ID } from '@angular/core';
import { Router, ActivatedRoute } from '@angular/router';
import { HttpClient, HttpHeaders, HttpParams, HttpErrorResponse } from '@angular/common/http';
import { environment } from '../../environments/environment';

import { Device, Location, Command, Capability, Parameter, Zone } from '../user-data.service';

export interface FNFeedback {
  // information for backend
  time: string;
  device: Device;
  command: Command;
  // position of the feedback in vis
  top: string;
  left: string;
}

export interface FPFeedback {
  log_id: number;
  time_str: string;
  entry_id: number;
  entry_id_ui: number;
}

export interface SyntaxFeedback {
  rule_id?: number;
  mode: string;  // 'add-cond', 'change-cond-param', 'change-cond', 'add-rule', 'change-trigger'
  cond_id?: number;
}

@Injectable({
  providedIn: 'root'
})
export class RsiService {
  // the current device/command we are working on
  public currentDevice: Device;
  public currentCommand: Command;

  // the current location id we are working on
  public currentLoc: number;

  // mode: Which interface to use? 
  // control (c), syn_feed (sf), syn_nofeed(sn), nosyn_feed(nf), nosyn_nofeed(nn)
  public mode: string;

  // for device/cap selection page
  public devices: Device[];
  public currentZone: Zone;
  public currentDev: Device;

  // which device capability the user selected 
  public modification: number;
  
  // service variable to store vis data fetched
  public visData: any;
  
  // this is for FN feedback
  // it saved the time at the feedback click
  public currentFeedbackTime: string;

  public currentLogId: number;
  public currentTimeStr: string;
  public currentEntryId: number;

  // mode for behavior feedback interfaces
  public currentMode: boolean;  // true: fn, false: fp

  // the saved behavior feedback
  public currentFNFeedbacks: FNFeedback[]; //this is for the time?
  public currentFPFeedbacks: Map<string, FPFeedback> = new Map<string, FPFeedback>(); // map "log_id,time_str,entry_id_ui" to FPFeedback

  // the saved syntax feedback
  public currentSyntaxFeedbacks: SyntaxFeedback[];

  // mode for syntax feedback interfaces
  public currentSyntaxMode: number;  // 0: change a condition, 1: add a condition, 2: add a new rule
  public currentConditionText: string;  // the selected condition text
  public currentConditionValue: string;  // the value in the selected condition
  public currentConditionId: number;  // the condition id within a rule
  public currentRuleId: number;  // the rule id (in the list, not the id at backend)

  // a dictionary showing which conditions are modified
  // entry: (rule_id, condition_id), (rule_id, -1) for adding condition
  //        (-1, -1) for adding rule
  //        condition_id is the interface cond id where 0 is the trigger
  public syntaxFbDict: Set<string> = new Set<string>();

  // token to be used when sending feedbacks
  public cache_token: string;

  // the api url root for backend apis
  private apiUrl: string = environment.apiUrl;

  constructor(private router: Router, private route: ActivatedRoute,
    private http: HttpClient, @Inject(LOCALE_ID) public locale: string) { }

  // navigates to device selector
  public gotoDeviceSelector(zone: Zone): void {
    this.currentZone = zone;
    this.router.navigate(['synthesize/devsel'], { relativeTo: this.route });
  }

  // navigates to synthesis dashboard
  public gotoDashboard(device: Device): void {
    this.currentDev = device;
    this.router.navigate(['synthesize/dashboard'], { relativeTo: this.route });
  }

  public gotoSynthesize(): void {
    this.router.navigate(["synthesize"], { relativeTo: this.route });
  }

  public gotoDebug(): void {
    this.router.navigate(["debug"], { relativeTo: this.route });
  }

  public gotoFeedback(): void {
    this.router.navigate(["manualfeedback"], { relativeTo: this.route });
  }

  public gotoSyntaxFb(): void {
    this.router.navigate(["syntaxfeedback"], { relativeTo: this.route });
  }

  public gotoResult(): void {
    this.router.navigate(["result"], { relativeTo: this.route });
  }

  public showCommand(count: number, covered: number, reverted: number, mode: string): boolean {
    if (mode == 'c') {
      return false;
    } else if (mode == 'sf' || mode == 'nf') {
      return count > 0;
    } else {
      return count - covered >= 3 || reverted >= 2;
    }
  }

  public tupleToStr(rule_i: number, cond_i: number) {
    return rule_i.toString() + ',' + cond_i.toString();
  }

  // Get rules related to one action (for syntax feedback)
  public getRulesForSyntaxFb(device: Device, command: Command) {
    let body = { "device": device, "command": command, "locid": this.currentLoc };
    let option = { headers: new HttpHeaders().set('Content-Type', 'application/json') };
    return this.http.post(this.apiUrl + "autotap/getrulesforsyntax/", body, option);
  }

  // Send the final feedback. Field is decided according to the mode.
  // this.fnFeedbacks, this.fpFeedbacks, this.syntaxFeedbacks might be sent based on this.mode
  public sendFeedback(device: Device, command: Command, isAlt = false) {
    let fn_feedbacks = this.currentFNFeedbacks.map(fb => {
      return {'time': fb.time, 'device': fb.device, 'command': fb.command};
    });
    let fp_feedbacks = Array.from(this.currentFPFeedbacks.values()).map(fb => {
      return {'log_id': fb.log_id, 'time_str': fb.time_str, 'entry_id': fb.entry_id};
    });
    let body = {
      "fn_feedbacks": fn_feedbacks, "fp_feedbacks": fp_feedbacks,
      "syntax_feedbacks": this.currentSyntaxFeedbacks, "request_token": this.cache_token,
      "locid": this.currentLoc, "device": device, "command": command, 'is_alt': isAlt
    };
    let option = { headers: new HttpHeaders().set('Content-Type', 'application/json') };
    return this.http.post(this.apiUrl + "autotap/sendfeedback/", body, option);
  }

  public fetchLogForVis(token: string) {
    let body = {"vis_token": token, "locid": this.currentLoc};
    let option = {headers: new HttpHeaders().set('Content-Type', 'application/json')};
    return this.http.post(this.apiUrl + "autotap/getepisode/", body, option);
  }

  // Get log for manual feedback
  public fetchLogForFeedback(device: Device, command: Command) {
    let body = { "device": device, "command": command, "first_time": true, "locid": this.currentLoc };
    let option = { headers: new HttpHeaders().set('Content-Type', 'application/json') };
    return this.http.post(this.apiUrl + "autotap/getepisodeformanualfeedback/", body, option);
  }

  public clearFeedback() {
    this.currentFNFeedbacks = [];
    this.currentFPFeedbacks.clear();
  }

  // Add a FN feedback
  public addFNFeedback(time: string, top: string, left: string) {
    this.currentFNFeedbacks.push({
      'time': time,
      'device': this.currentDevice,
      'command': this.currentCommand,
      'top': top,
      'left': left
    });
  }

  // Remove a FN feedback
  public removeFNFeedback(id: number) {
    this.currentFNFeedbacks.splice(id, 1);
  }

  // Add a FP feedback
  public addFPFeedback(logId: number, timeStr: string, entryId: number, entryIdUi: number) {
    this.currentFPFeedbacks.set(logId+","+timeStr+","+entryIdUi, {
      'log_id': logId,
      'time_str': timeStr,
      'entry_id': entryId,
      'entry_id_ui': entryIdUi
    });
  }

  // Remove a FP feedback
  public removeFPFeedback(logId: number, timeStr: string, entryId: number, entryIdUi: number) {
    if (this.currentFPFeedbacks.has(logId+","+timeStr+","+entryIdUi))
      this.currentFPFeedbacks.delete(logId+","+timeStr+","+entryIdUi);
  }
}

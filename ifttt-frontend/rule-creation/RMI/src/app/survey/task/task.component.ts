import { Component, OnInit, OnDestroy } from '@angular/core';
import { interval } from 'rxjs/internal/observable/interval';
import { Subscription } from 'rxjs';
import { startWith, switchMap } from 'rxjs/operators';
import { Router, ActivatedRoute } from '@angular/router';
import { MatDialog } from '@angular/material';

import { UserDataService, Rule, RuleUIRepresentation } from '../../user-data.service';
import { SurveyService } from '../survey.service';
import { CurrentruleComponent } from '../../rsi/currentrule/currentrule.component';
import { InstructionsComponent } from '../instructions/instructions.component';

export interface ScenarioPage {
  position: number,
  texts: any[],
  image: string,
  title: string,
  needcondition: boolean,
  showrules: boolean
}

@Component({
  selector: 'app-task',
  templateUrl: './task.component.html',
  styleUrls: ['./task.component.css']
})
export class TaskComponent implements OnInit {

  timeInterval: Subscription;
  public allowProceed: boolean = false;
  public uploadClicked: boolean = false;
  public pages: ScenarioPage[];
  public taskid: number;
  public firstpos: number;
  public lastpos: number;

  private unparsedRules: Rule[];
  public RULES: RuleUIRepresentation[];

  public mode: string;

  constructor(
    private userDataService: UserDataService,
    private surveyService: SurveyService,
    private dialog: MatDialog, 
    private route: Router,
    private router: ActivatedRoute
  ) { }

  ngOnInit() {
    let flag = this.route.url.split('/')[2];
    flag = flag == 'tutorial' ? 't' : 's';  
    this.userDataService.getCsrfCookie().subscribe(dataCookie => {
      this.router.params.subscribe(params => {
        let usercode = params['usercode'];
        let taskid = params['taskid'];
        this.taskid = taskid;

        this.userDataService.getScenarioInfo(usercode, flag, taskid).subscribe(res => {
          this.mode = res['user_mode'];
          this.pages = res['pages'].map(page => {
            return {
              'position': page.position,
              'texts': this.surveyService.parseText(page.text),
              'image': page.image,
              'title': page.title,
              'needcondition': page.needcondition,
              'showrules': page.showrules
            }
          });

          if (this.pages) {
            console.error('pages should not be empty! ');
          }

          this.firstpos = this.pages[0].position;
          this.lastpos = this.pages[this.pages.length-1].position;
          this.unparsedRules = res['rules'];

          this.userDataService.current_loc = res['loc_id'];
          this.userDataService.token = res['loc_token'];

          // if (this.mode != 'sn' && this.mode != 'nn') {
          //   this.timeInterval = interval(1500).pipe(
          //     startWith(0),
          //     switchMap(()=>this.userDataService.getMonitoredDevStatus(this.userDataService.current_loc))
          //   ).subscribe(
          //     res => {
          //       if (res["proceed"])
          //         this.allowProceed = true;
          //     },
          //     console.error
          //   );
          // }
          
          this.RULES = this.userDataService.parseRules(this.unparsedRules);
        });
      });
    });
  }

  uploadTrace() {
    this.uploadClicked = true;
    if (this.mode != 'sn' && this.mode != 'nn') {
      console.error("We should not upload traces in explicit feedback mode.");
    }
    this.surveyService.uploadTrace(this.userDataService.current_loc).subscribe(res => {
      this.timeInterval = interval(1500).pipe(
        startWith(0),
        switchMap(()=>this.userDataService.getMonitoredDevStatus(this.userDataService.current_loc))
      ).subscribe(
        res => {
          if (!res["pending_trace"])
            this.allowProceed = true;
        },
        console.error
      );
    });
  }

  showCurrentRules() {
    const dialogRef = this.dialog.open(CurrentruleComponent, {
      data: {rules: this.RULES}
    });
  }

  showInstructions(token) {
    const dialogRef = this.dialog.open(InstructionsComponent, {
      data: {token: token}
    });
  }

  gotoRulePage() {
    const url = this.route.serializeUrl(
      this.route.createUrlTree(["/rules"])
    );
    window.open(url, '_blank');
  }

  ngOnDestroy() {
    if (this.timeInterval)
      this.timeInterval.unsubscribe();
  }
}

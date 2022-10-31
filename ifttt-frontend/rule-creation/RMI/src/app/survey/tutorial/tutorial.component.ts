import { Component, OnInit, OnDestroy } from '@angular/core';
import { interval } from 'rxjs/internal/observable/interval';
import { Subscription } from 'rxjs';
import { startWith, switchMap } from 'rxjs/operators';
import { Router, ActivatedRoute } from '@angular/router';

import { UserDataService, Rule } from '../../user-data.service';
import { SurveyService } from '../survey.service';

export interface RuleUIRepresentation {
  words: string[]; // e.g. IF, AND, THEN
  icons: string[]; // the string name of the icons
  descriptions: string[]; // the descriptions for each of the icons
}

export interface ScenarioPage {
  position: number,
  text: string,
  image: string,
  title: string,
  needcondition: boolean,
  showrules: boolean
}

@Component({
  selector: 'app-tutorial',
  templateUrl: './tutorial.component.html',
  styleUrls: ['./tutorial.component.css']
})
export class TutorialComponent implements OnInit {

  timeInterval: Subscription;
  public allowProceed: boolean = false;
  public pages: ScenarioPage[];
  public taskid: number;

  private unparsedRules: Rule[];
  public RULES: RuleUIRepresentation[];

  constructor(
    private userDataService: UserDataService,
    private surveyService: SurveyService,
    private route: Router,
    private router: ActivatedRoute
  ) { }

  ngOnInit() {
    this.userDataService.getCsrfCookie().subscribe(dataCookie => {
      this.router.params.subscribe(params => {
        let usercode = params['usercode'];
        let taskid = params['taskid'];
        this.taskid = taskid;

        this.surveyService.getScenarioInfo(usercode, 't', taskid).subscribe(res => {
          this.pages = res['pages'];
          this.unparsedRules = res['rules'];
          
          this.userDataService.current_loc = res['loc_id'];
          this.userDataService.token = res['loc_token'];
          
          this.timeInterval = interval(1500).pipe(
            startWith(0),
            switchMap(()=>this.userDataService.getMonitoredDevStatus(this.userDataService.current_loc))
          ).subscribe(
            res => {
              if (res["proceed"])
                this.allowProceed = true;
            },
            console.error
          );

          this.RULES = this.userDataService.parseRules(this.unparsedRules);
        });
      });
    });
  }

  ngOnDestroy() {
    this.timeInterval.unsubscribe();
  }

}

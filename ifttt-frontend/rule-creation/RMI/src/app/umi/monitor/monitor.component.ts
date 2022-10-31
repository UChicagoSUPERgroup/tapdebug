import { Component, OnInit, OnDestroy } from '@angular/core';
import { interval } from 'rxjs/internal/observable/interval';
import { Subscription } from 'rxjs';
import { startWith, switchMap } from 'rxjs/operators';
import { UserDataService } from '../../user-data.service';

@Component({
  selector: 'app-monitor',
  templateUrl: './monitor.component.html',
  styleUrls: ['./monitor.component.css']
})
export class MonitorComponent implements OnInit, OnDestroy {

  timeInterval: Subscription;
  constructor(
    private userDataService: UserDataService
  ) { }

  public devNames: string[];
  public devValues: string[];

  ngOnInit() {
    this.userDataService.getCsrfCookie().subscribe(
      res => {
          this.userDataService.getLocationToken().subscribe(
              res => {
                  console.log(res['locid']);
                  this.userDataService.current_loc = res["locid"];
                  this.userDataService.token = res["token"];
                  this.userDataService.mode = res["mode"];
                  this.userDataService.isLoggedIn = true;

                  this.timeInterval = interval(1500).pipe(
                    startWith(0),
                    switchMap(()=>this.userDataService.getMonitoredDevStatus(this.userDataService.current_loc))
                  ).subscribe(
                    res => {
                      this.devNames = res["monitors"].map(x=>x.device.name);
                      this.devValues = res["monitors"].map(x=>x.value);
                    },
                    console.error
                  )
              }
          )
      }
    );
  }

  ngOnDestroy() {
    this.timeInterval.unsubscribe();
  }
}

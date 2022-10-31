import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { UserDataService, Device } from '../../user-data.service';

@Component({
  selector: 'app-visualization',
  templateUrl: './visualization.component.html',
  styleUrls: ['./visualization.component.css']
})
export class VisualizationComponent implements OnInit {

  public devices: Device[];
  public showSpinner: boolean = true;
  public selection: boolean[][][] = [];
  public start_date: string;
  public start_time: string;
  public end_date: string;
  public end_time: string;

  constructor(private userDataService: UserDataService, private route: Router) { }

  ngOnInit(): void {
    this.userDataService.getLocationToken().subscribe(u_data => {
      // this.userDataService.getDevices(this.userDataService.current_loc, false, false).subscribe(data => {
      //   this.devices = data['devs'];
      //   // initialize selection bits
      //   for (let d_i in this.devices)
      //   {
      //     this.selection.push([]);
      //     for (let c_i in this.devices[d_i].capabilities)
      //     {
      //       this.selection[d_i].push([]);
      //       for (let p_i in this.devices[d_i].capabilities[c_i]["parameters"])
      //       {
      //         this.selection[d_i][c_i].push(false);
      //       }
      //     }
      //   }
      //   this.showSpinner = false;
      // });
    });
  }

  goToDashboard() {
    this.route.navigate(["/admin"]);
  }

  submit() {
    this.userDataService.visEntities = [];
    for (let d_i in this.devices)
    {
      for (let c_i in this.devices[d_i].capabilities)
      {
        for (let p_i in this.devices[d_i].capabilities[c_i]["parameters"])
        {
          if(this.selection[d_i][c_i][p_i])
          {
            let entity = {
              "device": this.devices[d_i],
              "capability": this.devices[d_i].capabilities[c_i],
              "parameter": this.devices[d_i].capabilities[c_i]['parameters'][p_i]
            };
            this.userDataService.visEntities.push(entity);
          }
        }
      }
    }
    let start_datetime = this.start_date + ' ' + this.start_time;
    let end_datetime = this.end_date + ' ' + this.end_time;
    this.userDataService.startDatetime = start_datetime;
    this.userDataService.endDatetime = end_datetime;
    this.route.navigate(["/admin/visbase"]);
  }
}

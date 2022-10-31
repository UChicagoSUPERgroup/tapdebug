import { Component} from '@angular/core';
import { Location } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { UserDataService, Device } from '../../user-data.service';

@Component({
  selector: 'app-device-selector',
  templateUrl: './device-selector.component.html',
  styleUrls: ['./device-selector.component.css']
})
export class DeviceSelectorComponent {

  public selectedZoneID: number;
  public selectableDevices: Device[];

  constructor(private userDataService: UserDataService, private router: ActivatedRoute, public _location: Location) {
    this.router.params.subscribe(params => {
      this.selectedZoneID = params["zone_id"];
    });
    this.userDataService.getDevicesInLocation((this.userDataService.currentObjectType == "trigger"), 
                                               this.userDataService.isCurrentObjectEvent, this.selectedZoneID)
                        .subscribe(
                          data => { this.selectableDevices = data["devs"]; }
                        );
  }
}

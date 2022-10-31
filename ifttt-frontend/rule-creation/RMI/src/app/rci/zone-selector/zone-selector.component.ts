import { Component, OnInit } from '@angular/core';
import { Location } from '@angular/common';

import { UserDataService, Zone } from '../../user-data.service';

@Component({
  selector: 'app-zone-selector',
  templateUrl: './zone-selector.component.html',
  styleUrls: ['./zone-selector.component.css']
})
export class ZoneSelectorComponent implements OnInit {

  public selectableZones: Zone[];

  constructor(private userDataService: UserDataService, public _location: Location) {
    this.userDataService.getZones()
        .subscribe(data => {
                    this.selectableZones = data["zones"];
                  });
  }

  ngOnInit() {
  }

}

import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { Location } from '@angular/common';

import { UserDataService, Device, Command, Capability, Parameter, Zone } from '../../user-data.service';
import { RsiService } from '../rsi.service';

@Component({
  selector: 'app-devsel',
  templateUrl: './devsel.component.html',
  styleUrls: ['./devsel.component.css']
})
export class DevselComponent implements OnInit {

  public currentZone: Zone;
  public selectableDevices: Device[];

  constructor(
    public userDataService: UserDataService,
    public rsiService: RsiService,
    private route: Router,
    public _location: Location) {
  }

  ngOnInit() {
    this.currentZone = this.rsiService.currentZone;
    this.getDevices();
  }

  getDevices() {
    this.selectableDevices = this.rsiService.devices.filter(dev => {
      if (dev.zone.id != this.currentZone.id)
        return false;
      for (let command of dev.commands)
        if (this.rsiService.showCommand(command.count, command.covered, command.reverted, this.rsiService.mode))
          return true;
      return false
    });
  }

  goBack() {
    this.route.navigate(["synthesize/zonesel"]);
  }
}

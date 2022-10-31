import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { Location } from '@angular/common';

import { UserDataService, Device, Command, Capability, Parameter, Zone } from '../../user-data.service';
import { RsiService } from '../rsi.service';

@Component({
  selector: 'app-zonesel',
  templateUrl: './zonesel.component.html',
  styleUrls: ['./zonesel.component.css']
})
export class ZoneselComponent implements OnInit {

  public selectableZones: Zone[];
  public selectableDevices: Device[];
  public device: Device;

  public currentDeviceCommandCapabilities: any[];
  public currentCommands: Command[];
  public showSpinner: boolean = true;

  // the height of each expansion panel
  public collapsedHeight = "64px";

  // step: 1 - zone; 2 - device; 3 - action
  public step = 1;
  public enabledStep = 1;

  // "<command_id>,<fp/fn>"
  public stmtSelection: string = "";
  public fetchingViz = false;

  constructor(
    public userDataService: UserDataService,
    public rsiService: RsiService,
    private route: Router,
    public _location: Location) { }

  ngOnInit() {
    this.userDataService.getLocationToken().subscribe(res => {
      this.userDataService.current_loc = res["locid"];
      this.userDataService.token = res["token"];
      this.userDataService.mode = res["mode"];
      
      this.rsiService.currentLoc = this.userDataService.current_loc;
      this.rsiService.mode = this.userDataService.mode;
      this.userDataService.getDevices(this.userDataService.current_loc).subscribe(
        data => {
          this.rsiService.devices = data["devs"];
          this.getZones();
          this.showSpinner = false;
        },
        err => {
            if(err.status == 403) {
                this.route.navigate(["/error/403"]);
            }
        });
    });
    // this.sideNavOpened = false;
  }

  getZones() {
    let zoneSet = new Set<number>();
    this.selectableZones = [];
    for (let dev of this.rsiService.devices) {
      for (let command of dev.commands) {
        if (this.rsiService.showCommand(command.count, command.covered, command.reverted, this.rsiService.mode)) {
          // NOTE: since users can provide feedback, we allow all events that happened before
          if (!zoneSet.has(dev.zone.id)) {
            zoneSet.add(dev.zone.id);
            this.selectableZones.push(dev.zone);
          }
          break;
        }
      }
    }
  }

  getDeviceCommandCapabilities(device: Device) {
    let capList = [];
    for (let command of device.commands) {
      if (!capList.map(cap => cap[0].id).includes(command.capability.id)) {
        capList.push([command.capability, command.parameter]);
      }
    }
    return capList;
  }

  getDefaultTextForCapability(capability: Capability, parameter: Parameter) {
    return this.userDataService.getDefaultTextForCapability(capability, parameter);
  }

  getCommandFromCapability(device: Device, capability: Capability) {
    return device.commands.filter(x => x.capability.id == capability.id);
  }

  gotoDeviceSelector(zone: Zone) {
    this.rsiService.currentZone = zone;

    this.selectableDevices = this.rsiService.devices.filter(dev => {
      if (dev.zone.id != zone.id)
        return false;
      for (let command of dev.commands)
        if (this.rsiService.showCommand(command.count, command.covered, command.reverted, this.rsiService.mode))
          return true;
      return false
    });

    this.setStep(2);
  }

  gotoDashboard(device: Device) {
    this.rsiService.currentDev = device;
    this.device = device;
    this.currentDeviceCommandCapabilities = this.getDeviceCommandCapabilities(device);
    this.currentCommands = [];
    for (let capability_parameter of this.currentDeviceCommandCapabilities) {
      this.currentCommands = this.currentCommands.concat(this.getCommandFromCapability(device, capability_parameter[0]));
    }
    this.currentCommands = this.currentCommands.filter(
      command => 
      ((command.count>0 || command.reverted>0) && 
       this.rsiService.showCommand(command.count, command.covered, command.reverted, this.userDataService.mode)));
    this.setStep(3);
  }

  openDialog(device: Device, command: Command) {
    this.rsiService.currentDevice = device;
    this.rsiService.currentCommand = command;
    this.rsiService.clearFeedback();
    if (this.rsiService.mode == 'nf') {
      this.route.navigate(["/choices"]);
      // this.rsiService.gotoFeedback();
    } else if (this.rsiService.mode == 'sn') {
      this.rsiService.gotoSyntaxFb();
    } else if (this.rsiService.mode == 'nn') {
      this.rsiService.gotoResult();
    } else {
      console.error("unknown interface type");
    }  
  }

  submitSelection() {
    let selTup = this.stmtSelection.split(",");
    let selId = selTup[0];
    let selMode = selTup[1];
    let command = this.currentCommands[selId];

    this.rsiService.currentDevice = this.rsiService.currentDev;
    this.rsiService.currentCommand = command;
    this.rsiService.clearFeedback();

    this.rsiService.modification = selMode == "fp" ? 2 : 1;

    this.fetchingViz = true;
    if (this.rsiService.mode == 'nf') {
      this.rsiService.fetchLogForFeedback(this.rsiService.currentDevice, this.rsiService.currentCommand).subscribe(data => {
        // store vis data
        this.rsiService.visData = data;
        this.rsiService.gotoFeedback();
      });
    } else if (this.rsiService.mode == 'nn') {
      this.rsiService.gotoResult();
    } else if (this.rsiService.mode == 'sn') {
      this.rsiService.gotoSyntaxFb();
    } else {
      console.error("unknown interface type");
    }
    
  }

  setStep(step) {
    this.step = step;
    this.enabledStep = this.enabledStep < step ? step : this.enabledStep;
  }

  goBack() {
    this.route.navigate(["rules"]);
  }
}

import { Component, OnInit } from '@angular/core';
import { Router, ActivatedRoute } from '@angular/router';
import { Location as _Location } from '@angular/common';
import { MatDialog } from '@angular/material';
import { MatBottomSheet } from '@angular/material/bottom-sheet';
import { ModeselComponent } from '../modesel/modesel.component';
import { UserDataService, Device, Location, Command, Capability, Parameter } from '../../user-data.service';
import { RsiService } from '../rsi.service';

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent implements OnInit {

  public username: string;
  public device: Device;
  public locations: Location[];

  constructor(
    public userDataService: UserDataService,
    public rsiService: RsiService,
    private route: Router,
    private router: ActivatedRoute,
    private dialog: MatDialog,
    public _location: _Location) { 
  }

  ngOnInit() {
    this.device = this.rsiService.currentDev;
  }

  getDeviceCommandCapabilities(device: Device) {
    let capList = [];
    for (let command of device.commands) {
      if (!capList.map(cap => cap[0].id).includes(command.capability.id)) {
        capList.push([command.capability, command.parameter]);
      }
      
      
    }
    //console.log(capList)
    return capList;
  }

  getCommandFromCapability(device: Device, capability: Capability) {
    //console.log(device.commands.filter(x => x.capability.id == capability.id))
    return device.commands.filter(x => x.capability.id == capability.id);
  }

  getDefaultTextForCapability(capability: Capability, parameter: Parameter) {
    return this.userDataService.getDefaultTextForCapability(capability, parameter);
  }

  logout() {
    this.userDataService.logout().subscribe(data => {
      this.userDataService.username = null;
      this.userDataService.isLoggedIn = false;
      this.userDataService.current_loc = -1;
      this.route.navigate(["/"]);
    });
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
      this.dialog.open(ModeselComponent);
    }
    
  }

  goToRsiBase(device: Device, command: Command) {
    this.rsiService.currentDevice = device;
    this.rsiService.currentCommand = command;
    this.route.navigate(["/synthesize"]);
  }

  goToDashboard() {
    this.route.navigate(["/rules"]);
  }

  gotoCreate() {
    delete this.userDataService.currentlyStagedRule;
    localStorage['currentlyStagedRuleIndex'] = -1;
    this.route.navigate(["/create"]);
  }

  goBack() {
    this.route.navigate(["synthesize/devsel"]);
  }
}

import { Component, OnInit } from '@angular/core';
import {
  //cut down imports
  ViewChild,
  ViewContainerRef,
  ComponentFactoryResolver,
  ComponentRef,
  ComponentFactory
} from '@angular/core';

import { Router, ActivatedRoute } from '@angular/router';
import { Location as _Location } from '@angular/common';
import { MatDialog } from '@angular/material';
import { CurrentruleComponent } from '../currentrule/currentrule.component';
import { VisbaseComponent } from '../vis/visbase/visbase.component';
import { ModeselComponent } from '../modesel/modesel.component';

import { UserDataService, Device, Location, Command, Rule, Capability } from '../../user-data.service';
import { RsiService } from '../rsi.service';

@Component({
  selector: 'app-choices',
  templateUrl: './choices.component.html',
  styleUrls: ['./choices.component.css']
})
export class ChoicesComponent implements OnInit {

  public device: Device;
  public modification: number;
  public devv: Device;
  public cmd: Command;

  // show spinner when it result has not been fetched
  public showSpinner: boolean = true;

  constructor(
    public userDataService: UserDataService,
    public rsiService: RsiService,
    private resolver: ComponentFactoryResolver, private dialog: MatDialog,
    private route: ActivatedRoute,
    private router: Router,
    public _location: _Location) { }

  ngOnInit() {
    this.device = this.rsiService.currentDev;
    this.modification = this.rsiService.modification;
    this.devv = this.rsiService.currentDevice;
    this.cmd = this.rsiService.currentCommand;

    let dataFetched: boolean = false;
    this.route.paramMap.subscribe(params => {
      if (params.has('dataFetched'))
        dataFetched = params.get('dataFetched') == 'true';
      if (!dataFetched) {
        this.rsiService.fetchLogForFeedback(this.devv, this.cmd).subscribe(data => {
          // store vis data
          this.rsiService.visData = data;
          // show options
          this.showSpinner = false;
        });
      } else {
        this.showSpinner = false;
      }
    });
  }

  public getCurrentCommandText() { //to remind user of what they picked in dashboard
    return this.userDataService.getTextFromParVal(this.devv, 
                                                  this.cmd.capability, 
                                                  [this.cmd.parameter], 
                                                  [{"value": this.cmd.value,
                                                    "comparator": "="}]);
  }

  openDialog(device: Device, command: Command, choice: number) {
    // this information is to guide the next vis page
    // visual hints and options on next page is determined 
    // on this.rseService.modification
    this.rsiService.modification = choice;

    this.rsiService.currentDevice = device;
    this.rsiService.currentCommand = command;
    
    // this page should be followed by the behavior
    // feedback interface
    this.rsiService.gotoFeedback();
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

  getCommandFromCapability(device: Device, capability: Capability) {
    return device.commands.filter(x => x.capability.id == capability.id);
  }

  readModificationVariable() {
    console.log("Previous Choice(button click): ", this.rsiService.modification);
  }

  goBack() {
    this.router.navigate(["synthesize/zonesel"]);
  }
}

import {
  OnInit, 
  Component,
  ViewChild,
  ViewContainerRef,
  ComponentFactoryResolver,
  ComponentRef,
  ComponentFactory,
  ViewEncapsulation 
} from '@angular/core';
import { Pipe, PipeTransform } from '@angular/core';
import { Router } from '@angular/router';
import { Location as _Location } from '@angular/common';
import { MatDialog } from '@angular/material';

import { UserDataService, Rule, Device, Command } from '../../user-data.service';
import { RsiService } from '../rsi.service';
import { SyntaxfbComponent } from './syntaxfb/syntaxfb.component';

export interface RuleUIRepresentation {
  words: string[]; // e.g. IF, AND, THEN
  icons: string[]; // the string name of the icons
  descriptions: string[]; // the descriptions for each of the icons
  enhancedDesc?: string[][][]; // enhanced description highlighting locations
  has_numeric: string[];  // whether this statement has numeric values. if so, store the value
}

export interface RuleModificationStatus {
  cond_modified: boolean[];
  val_modified: boolean[];
  cond_modified_temp: boolean[];
  val_modified_temp: boolean[];
  cond_use_temp: boolean[];
  new_cond: boolean;
  new_cond_temp: boolean;
  new_use_temp: boolean;
}

export interface ModificationStatus {
  rules: RuleModificationStatus[];
  new_rule: boolean;
  new_rule_temp: boolean;
  new_use_temp: boolean;
}

@Pipe({
  name: 'modifywords',
  pure: false
})
export class ModifyWordsPipe implements PipeTransform {

  // based on how a rule is modified, return how should we show the rules
  transform(modifyStatus: ModificationStatus, rule_i: number, cond_i: number, RULES: RuleUIRepresentation[]): string[][] {
    let res = [];
    let enhancedDesc = RULES[rule_i].enhancedDesc[cond_i];
    for (let desc of enhancedDesc) {
      if (desc[0] == "location") {
        res.push(["location", desc[1]]);
      } else {
        if (modifyStatus.rules[rule_i].cond_use_temp[cond_i]) {
          if (modifyStatus.rules[rule_i].cond_modified_temp[cond_i]) {
            res.push(["highlight", desc[1]]);
          } else if (modifyStatus.rules[rule_i].val_modified_temp[cond_i]) {
            let str = desc[1];
            let value = RULES[rule_i].has_numeric[cond_i];
            let start_i = str.indexOf(value);
            if (start_i != -1) {
              if (start_i)
                res.push(["regular", str.slice(0, start_i)]);
              res.push(["highlight", value]);
              if (start_i+value.length < str.length)
                res.push(["regular", str.slice(start_i+value.length)]);
            } else {
              res.push(["regular", str]);
            }
            
          } else {
            res.push(["regular", desc[1]]);
          }
        } else {
          if (modifyStatus.rules[rule_i].cond_modified[cond_i]) {
            res.push(["highlight", desc[1]]);
          } else if (modifyStatus.rules[rule_i].val_modified[cond_i]) {
            let str = desc[1];
            let value = RULES[rule_i].has_numeric[cond_i];
            let start_i = str.indexOf(value);
            if (start_i != -1) {
              if (start_i)
                res.push(["regular", str.slice(0, start_i)]);
              res.push(["highlight", value]);
              if (start_i+value.length < str.length)
                res.push(["regular", str.slice(start_i+value.length)]);
            } else {
              res.push(["regular", str]);
            }
          } else {
            res.push(["regular", desc[1]]);
          }
        }
      }
    }
    
    // if (modifyStatus.rules[rule_i].cond_use_temp[cond_i]) {
    //   if (modifyStatus.rules[rule_i].cond_modified_temp[cond_i]) {
    //     res.push(["highlight", RULES[rule_i].descriptions[cond_i]]);
    //   } else if (modifyStatus.rules[rule_i].val_modified_temp[cond_i]) {
    //     let str = RULES[rule_i].descriptions[cond_i];
    //     let value = RULES[rule_i].has_numeric[cond_i];
    //     let start_i = str.indexOf(value);
    //     if (start_i)
    //       res.push(["regular", str.substr(0, start_i)]);
    //     res.push(["highlight", value]);
    //     if (start_i+value.length < str.length)
    //       res.push(["regular", str.substr(start_i+value.length)]);
    //   } else {
    //     res.push(["regular", RULES[rule_i].descriptions[cond_i]]);
    //   }
    // } else {
    //   if (modifyStatus.rules[rule_i].cond_modified[cond_i]) {
    //     res.push(["highlight", RULES[rule_i].descriptions[cond_i]]);
    //   } else if (modifyStatus.rules[rule_i].val_modified[cond_i]) {
    //     let str = RULES[rule_i].descriptions[cond_i];
    //     let value = RULES[rule_i].has_numeric[cond_i];
    //     let start_i = str.indexOf(value);
    //     if (start_i)
    //       res.push(["regular", str.substr(0, start_i)]);
    //     res.push(["highlight", value]);
    //     if (start_i+value.length < str.length)
    //       res.push(["regular", str.substr(start_i+value.length)]);
    //   } else {
    //     res.push(["regular", RULES[rule_i].descriptions[cond_i]]);
    //   }
    // }
    return res;
  }

}

@Component({
  selector: 'app-rsibases',
  templateUrl: './rsibases.component.html',
  styleUrls: ['./rsibases.component.css'],
  // encapsulation: ViewEncapsulation.None,
})
export class RsibasesComponent implements OnInit {

  public finishParsing: boolean = false;

  public RULES: RuleUIRepresentation[];
  public ruleids: number[];
  private unparsedRules: Rule[];
  
  private currentDevice: Device;
  private currentCommand: Command;

  public commandStatement: string;

  public modifyStatus: ModificationStatus;

  constructor(
    public userDataService: UserDataService, 
    public rsiService: RsiService,
    private resolver: ComponentFactoryResolver, private dialog: MatDialog, 
    private route: Router, 
    public _location: _Location) { }

  ngOnInit() {
    this.currentDevice = this.rsiService.currentDevice;
    this.currentCommand = this.rsiService.currentCommand;

    this.commandStatement = this.userDataService.getTextForCommand(this.currentDevice, this.currentCommand, false);

    this.rsiService.currentSyntaxFeedbacks = [];
    this.rsiService.syntaxFbDict = new Set<string>();

    this.rsiService.getRulesForSyntaxFb(this.currentDevice, this.currentCommand).subscribe(data => {
      this.unparsedRules = data["rules"];
      if (this.unparsedRules) {
        this.ruleids = this.unparsedRules.map(x => x.id);
        this.parseRules();
      }  
    });
  }

  // parse rules into displayable form for list
  // initializing modify status of rules
  private parseRules() {
    const rules = this.unparsedRules;
    this.RULES = rules.map((rule => {
      const words = [];
      const descriptions = [];
      const enhancedDesc = [];
      const icons = [];
      const has_numeric = [];

      // add the if clause stuff
      for (let i = 0; i < rule.ifClause.length; i++) {
        let clause = rule.ifClause[i];
        words.push(i == 0 ? "If" : (i > 1 ? "and" : "while"));
        icons.push(clause.channel.icon);
        // clause.text = this.userDataService.updateTextForTiming(clause.text);
        // convert UTC time to local time if clock is used
        // if (clause.text.startsWith('(Clock)')) {
        //   let strLocalTime = this.userDataService.UTCTime2LocalTime(clause.text.substr(-5, 5));
        //   clause.text = clause.text.replace(/\d{2}:\d{2}/, strLocalTime);
        // }
        const description = clause.text;
        descriptions.push(description);
        enhancedDesc.push(this.userDataService.parseLocationForRuleDescription(description));
        if (clause.parameters[0].type == "range" || clause.parameters[0].type == "time") {
          has_numeric.push(clause.parameterVals[0].value);
        } else {
          has_numeric.push("");
        }
      }

      // add the then clause
      words.push("then");
      const description = rule.thenClause[0].text;
      descriptions.push(description);
      enhancedDesc.push(this.userDataService.parseLocationForRuleDescription(description));
      icons.push(rule.thenClause[0].channel.icon);
      if (rule.thenClause[0].parameters[0].type == "range" || rule.thenClause[0].parameters[0].type == "time") {
        has_numeric.push(rule.thenClause[0].parameterVals[0].value);
      } else {
        has_numeric.push("");
      }

      const ruleRep: RuleUIRepresentation = {
        words: words,
        icons: icons,
        descriptions: descriptions,
        enhancedDesc: enhancedDesc,
        has_numeric: has_numeric
      };
      return ruleRep;
    }));
    // initialize modify status of every rule
    this.modifyStatus = this.emptyModifyStatus();
    this.finishParsing = true;
  }

  emptyModifyStatus(): ModificationStatus {
    let res = {
      rules: [],
      new_rule: false,
      new_rule_temp: false,
      new_use_temp: false
    };
    for (let rule of this.RULES) {
      res.rules.push({
        cond_modified: rule.descriptions.map(x => false),
        val_modified: rule.descriptions.map(x => false),
        cond_modified_temp: rule.descriptions.map(x => false),
        val_modified_temp: rule.descriptions.map(x => false),
        cond_use_temp: rule.descriptions.map(x => false),
        new_cond: false,
        new_cond_temp: false,
        new_use_temp: false
      });
    }
    return res;
  }

  prepareModifyCondition(rule_i: number, condition_i: number) {
    // initialize information in rsiService
    // we are modifying one condition
    this.rsiService.currentSyntaxMode = 0;
    this.rsiService.currentConditionText = this.RULES[rule_i].descriptions[condition_i];
    this.rsiService.currentRuleId = rule_i;
    this.rsiService.currentConditionId = condition_i-1;
    if (this.unparsedRules[rule_i].ifClause[condition_i].parameters[0].type != 'bin') {
      this.rsiService.currentConditionValue = this.unparsedRules[rule_i].ifClause[condition_i].parameterVals[0].value;
    } else {
      this.rsiService.currentConditionValue = null;
    }
  }

  modifyCondition(value_only: boolean) {
    this.parseFeedback(value_only);
  }

  addCondition(rule_i: number) {
    // initialize information in rsiService
    this.rsiService.currentSyntaxMode = 1;
    this.rsiService.currentRuleId = rule_i;

    this.parseFeedback(false);
  }

  addNewRule() {
    // initialize information in rsiService
    this.rsiService.currentSyntaxMode = 2;

    this.parseFeedback(false);
  }

  mouseOverModifyMenu(valueOnly: boolean=false) {
    // should highlight the modification
    let rule_i = this.rsiService.currentRuleId;
    let cond_i = this.rsiService.currentConditionId + 1;
    if (this.modifyStatus.rules[rule_i].cond_modified[cond_i]) {
      // already modified, should use the same mask
      this.modifyStatus.rules[rule_i].cond_modified_temp[cond_i] = true;
      this.modifyStatus.rules[rule_i].val_modified_temp[cond_i] = false;
    } else {
      this.modifyStatus.rules[rule_i].cond_modified_temp[cond_i] = !valueOnly;
      this.modifyStatus.rules[rule_i].val_modified_temp[cond_i] = valueOnly;
    }
    this.modifyStatus.rules[rule_i].cond_use_temp[cond_i] = true;
  }

  mouseOutModifyMenu() {
    // use permanent masks again
    let rule_i = this.rsiService.currentRuleId;
    let cond_i = this.rsiService.currentConditionId + 1;
    this.modifyStatus.rules[rule_i].cond_modified_temp[cond_i] = false;
    this.modifyStatus.rules[rule_i].val_modified_temp[cond_i] = false;
    this.modifyStatus.rules[rule_i].cond_use_temp[cond_i] = false;
  }

  mouseOverAddingCondition(rule_i: number) {
    // should show new condition in the interface
    this.modifyStatus.rules[rule_i].new_cond_temp = true;
    this.modifyStatus.rules[rule_i].new_use_temp = true;
  }

  mouseOutAddingCondition(rule_i: number) {
    // use permanent masks again
    this.modifyStatus.rules[rule_i].new_cond_temp = false;
    this.modifyStatus.rules[rule_i].new_use_temp = false;
  }

  finishFeedback() {
    this.route.navigate(["/result"]);
  }

  clear() {
    this.rsiService.currentSyntaxFeedbacks = [];
    this.rsiService.syntaxFbDict = new Set<string>();
    this.modifyStatus = this.emptyModifyStatus();
  }

  ruleConditionModified(rule_i: number, condition_i: number) {
    let tup = this.rsiService.tupleToStr(rule_i, condition_i);
    return this.rsiService.syntaxFbDict.has(tup);
  }

  ruleConditionValueModified(rule_i: number, condition_i: number) {
    let tup = this.rsiService.tupleToStr(rule_i, condition_i);
    tup = tup + ",v";
    return this.rsiService.syntaxFbDict.has(tup);
  }

  ruleConditionAdded(rule_i: number) {
    let tup = this.rsiService.tupleToStr(rule_i, -1);
    return this.rsiService.syntaxFbDict.has(tup);
  }

  newRuleAdded() {
    let tup = this.rsiService.tupleToStr(-1, -1);
    return this.rsiService.syntaxFbDict.has(tup);
  }

  parseFeedback(valueOnly: boolean) {
    if (this.rsiService.currentSyntaxMode == 0) {
      if (this.rsiService.currentConditionId < 0) {
        // change a trigger
        let syntaxMode = valueOnly ? 'change-trig-param' : 'change-trig';
        this.rsiService.currentSyntaxFeedbacks.push({
          'rule_id': this.rsiService.currentRuleId,
          'cond_id': this.rsiService.currentConditionId,
          'mode': syntaxMode
        });
        // let tup = this.rsiService.tupleToStr(this.rsiService.currentRuleId, 0);
        // if (valueOnly) {
        //   tup = tup + ",v";
        // }
        // if (!this.rsiService.syntaxFbDict.has(tup))
        //   this.rsiService.syntaxFbDict.add(tup);
        if (!valueOnly)
          this.modifyStatus.rules[this.rsiService.currentRuleId].cond_modified[0] = true;
        else
          this.modifyStatus.rules[this.rsiService.currentRuleId].val_modified[0] = true;
      } else {
        // change a condition
        let syntaxMode = valueOnly ? 'change-cond-param' : 'change-cond';
        this.rsiService.currentSyntaxFeedbacks.push({
          'rule_id': this.rsiService.currentRuleId,
          'cond_id': this.rsiService.currentConditionId,
          'mode': syntaxMode
        });
        // let tup = this.rsiService.tupleToStr(this.rsiService.currentRuleId, this.rsiService.currentConditionId+1);
        // if (valueOnly) {
        //   tup = tup + ",v";
        // }
        // if (!this.rsiService.syntaxFbDict.has(tup))
        //   this.rsiService.syntaxFbDict.add(tup);
        if (!valueOnly)
          this.modifyStatus.rules[this.rsiService.currentRuleId].cond_modified[this.rsiService.currentConditionId+1] = true;
        else
          this.modifyStatus.rules[this.rsiService.currentRuleId].val_modified[this.rsiService.currentConditionId+1] = true;
      }
    } else if (this.rsiService.currentSyntaxMode == 1) {
      // add a condition
      this.rsiService.currentSyntaxFeedbacks.push({
        'rule_id': this.rsiService.currentRuleId,
        'mode': 'add-cond'
      });
      // let tup = this.rsiService.tupleToStr(this.rsiService.currentRuleId, -1);
      // if (!this.rsiService.syntaxFbDict.has(tup))
      //     this.rsiService.syntaxFbDict.add(tup);
      this.modifyStatus.rules[this.rsiService.currentRuleId].new_cond = true;
    } else if (this.rsiService.currentSyntaxMode == 2) {
      // add a new rule
      this.rsiService.currentSyntaxFeedbacks.push({
        'mode': 'add-rule'
      });
      // let tup = this.rsiService.tupleToStr(-1, -1);
      // if (!this.rsiService.syntaxFbDict.has(tup))
      //     this.rsiService.syntaxFbDict.add(tup);
      this.modifyStatus.new_rule = true;
    }
  }
}

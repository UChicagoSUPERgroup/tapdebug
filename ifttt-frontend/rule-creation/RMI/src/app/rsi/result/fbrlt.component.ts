import { Component, OnInit, ViewEncapsulation, ViewContainerRef, ViewChild, ComponentFactoryResolver, ComponentRef } from '@angular/core';
import { Router, ActivatedRoute } from '@angular/router';
import { Location as _Location } from '@angular/common';

import { VisComponent } from '../vis/vis.component';
import { UserDataService, Rule } from '../../user-data.service';
import { RsiService } from '../rsi.service';

export interface ChangedRuleUIRepresentation {
  words: string[]; // e.g. IF, AND, THEN
  icons: string[]; // the string name of the icons
  descriptions: string[]; // the descriptions (text)
  enhancedDesc?: string[][][]; // the enhanced description highlighting the zone [["location", "Bedroom #3"] ... ]
  status: number;  // -1: delte, 0: regular, 1: added
  statuses?: number[]; // -1: delete, 0: regular, 1: added, 21: changed (left), 22: changed (right), 101: placeholder (left), 102: placeholder (right)
  devCapIds: string[]; // "devId,capId", used to show meta info about a certain device
}

export interface ChangedRuleUIRepresentationPair {
  left: ChangedRuleUIRepresentation;
  right: ChangedRuleUIRepresentation
}

export interface RuleUIRepresentation {
  words: string[]; // e.g. IF, AND, THEN
  icons: string[]; // the string name of the icons
  descriptions: string[]; // the descriptions for each of the icons
  enhancedDesc?: string[][][]; // the enhanced description highlighting the zone [["location", "Bedroom #3"] ... ]
  modes: number[]; // 0: regular, 1: deleted, 2: added
  devCapIds: string[];
}

export interface PatchMeta {
  mode: any;
  rule_id: number;
  patches: any[];
}

@Component({
  selector: 'app-fbrlt',
  templateUrl: './fbrlt.component.html',
  styleUrls: ['./fbrlt.component.css'],
  encapsulation: ViewEncapsulation.None,
})
export class FbrltComponent implements OnInit {

  private patchClusters: PatchMeta[];
  private unparsedOrigRules: Rule[];

  public showSpinner: boolean = true;
  public currentCluster: number = 0;
  public clusterNum: number = 0;

  public clusterDescription: string;
  public RULES: RuleUIRepresentation[];

  public PROGRAM_TABLE: ChangedRuleUIRepresentationPair[];

  public patchMetaDescriptions: string[];

  public showAlternatives: boolean = false;
  public devCapMetas: any = {};  // show maximum/minimum value of a devCap in the history

  public isAlt = false;  // whether these are alternative results assuming participants select the wrong option

  // the following things are all for visualization for a rule
  private vis_token: string;
  public logFetched: boolean = false;  // flag indicating whether vis is ready
  private traceLogsFN: any[];
  private traceLogsTEC: any[];
  private traceLogsNI: any[];
  private devList: string[];
  private capList: string[];
  private targetId: number;
  private tapSensorList: any[];
  private ruleMasksFN: any[];
  private ruleMasksTEC: any[];
  private ruleMasksNI: any[];
  private nRevert: number;

  private refVis: ComponentRef<VisComponent>;

  @ViewChild('viscontainer', { read: ViewContainerRef }) entry: ViewContainerRef;
  constructor(
    public userDataService: UserDataService, 
    public rsiService: RsiService, 
    private route: Router, 
    private activatedRoute: ActivatedRoute,
    public _location: _Location,
    private resolver: ComponentFactoryResolver
  ) { }

  ngOnInit() {
    this.activatedRoute.paramMap.subscribe(params => {
      let isAlt = false;
      if (params.has('alt')) {
        isAlt = params.get('alt') == 'true';
      }
      this.isAlt = isAlt;
      this.rsiService.sendFeedback(this.rsiService.currentDevice, this.rsiService.currentCommand, isAlt).subscribe(resp => {
        this.rsiService.clearFeedback();
        
        this.patchClusters = resp["patches"];
        this.unparsedOrigRules = resp["orig_rules"];
        this.parseDevCapMeta(resp["trace_meta"]["min_max"]);
  
        if (!this.patchClusters.length) {
          this.showSpinner = false;
          this.clusterDescription = "No patches found.";
        } else {
          this.clusterNum = this.patchClusters.length;
          this.currentCluster = 0;
  
          this.parseCluster();
  
          this.showSpinner = false;
          this.vis_token = resp["vis_token"];
          if (!isAlt)
            this.fetchLog();
          else
            this.logFetched = true;
        }
      });
    });
  }

  // add a new condition to the right of the table
  private addConditionHelper(right: ChangedRuleUIRepresentation, clause) {
    if (right.descriptions[1] == "") {
      // initially right has no conditions
      // should replace the placeholder
      right.words[1] = "while";
      right.icons[1] = "";
      right.descriptions[1] = clause.text;
      right.enhancedDesc[1] = this.userDataService.parseLocationForRuleDescription(clause.text);
      right.statuses[1] = 1;
      right.devCapIds[1] = clause.device.id + ',' + clause.capability.id;
    } else {
      // right already has some conditions
      // should append at the end
      // we assume that right.words.length % 3 == 0
      // then we are adding 3 entries (2 placeholders)
      right.words.push('');
      right.descriptions.push('');
      right.enhancedDesc.push([]);
      right.icons.push('');
      right.statuses.push(0);
      right.devCapIds.push(',');

      right.words.push("and");
      right.icons.push("");
      right.descriptions.push(clause.text);
      right.enhancedDesc.push(this.userDataService.parseLocationForRuleDescription(clause.text));
      right.statuses.push(1);
      right.devCapIds.push(',');

      right.words.push('');
      right.descriptions.push('');
      right.enhancedDesc.push([]);
      right.icons.push('');
      right.statuses.push(0);
      right.devCapIds.push(',');
    }
  }

  // delete a condition within a rule
  // the cond_id is the real condition in the list
  private deleteConditionHelper(right: ChangedRuleUIRepresentation, cond_id: number) {
    while(cond_id < right.words.length) {
      let next_cond_id = cond_id + 3;
      if (next_cond_id >= right.words.length) {
        right.descriptions[cond_id] = "";
        right.enhancedDesc[cond_id] = [];
        right.icons[cond_id] = "";
        right.statuses[cond_id] = 0;
        right.words[cond_id] = "";
        right.devCapIds.push(',');
      } else {
        right.descriptions[cond_id] = right.descriptions[next_cond_id];
        right.enhancedDesc[cond_id] = this.userDataService.parseLocationForRuleDescription(right.descriptions[cond_id]);
        right.icons[cond_id] = right.icons[next_cond_id];
        right.statuses[cond_id] = right.statuses[next_cond_id];
        right.words[cond_id] = right.words[next_cond_id];
        right.devCapIds[cond_id] = right.devCapIds[next_cond_id];
      }
      cond_id = next_cond_id;
    }
  }

  // modify a condition within a rule
  // the cond_id is the real condition in the list
  private modifyConditionHelper(right: ChangedRuleUIRepresentation, cond_id: number, clause) {
    right.icons[cond_id] = "";
    right.descriptions[cond_id] = clause.text;
    right.enhancedDesc = this.userDataService.parseLocationForRuleDescription(clause.text);
    right.statuses[cond_id] = 1;
    right.devCapIds[cond_id] = clause.device.id + ',' + clause.capability.id;
  }

  //parse current cluster into rule representations
  private parseCluster() {
    // patch syntax description at the beginning
    if (this.patchClusters[this.currentCluster].mode == 'modify-rule') {
      this.clusterDescription = "One rule can be modified:";
    } else if (this.patchClusters[this.currentCluster].mode == 'add-rule') {
      this.clusterDescription = "A new rule can be added:";
    } else if (this.patchClusters[this.currentCluster].mode == 'delete-rule') {
      this.clusterDescription = "One rule can be deleted:";
    } else {
      console.error('Unknown patch mode:', this.patchClusters[this.currentCluster].mode);
    }

    // detailed patch description after the patch
    this.parseMetaDescription();

    // helper function to translate a rule clause to a RuleUIRepresentation
    let ruleToRep = rule => {
      const words = [];
      const descriptions = [];
      const icons = [];
      const statuses = [];
      const devCapIds = [];
      const enhancedDesc = [];
      let description = "";
      // add the if clause stuff
      words.push("If");
      icons.push("");
      description = this.userDataService.getTextForClause(rule.ifClause[0]).text;
      descriptions.push(description);
      enhancedDesc.push(this.userDataService.parseLocationForRuleDescription(description));
      statuses.push(0);
      devCapIds.push(rule.ifClause[0].device.id+','+rule.ifClause[0].capability.id);

      if (rule.ifClause.length == 1) {
        // add empty while condition if needed
        words.push('');
        descriptions.push('');
        enhancedDesc.push([]);
        icons.push('');
        statuses.push(0);
        devCapIds.push(',');
      } else {
        // add the first while condition
        words.push("while");
        description = this.userDataService.getTextForClause(rule.ifClause[1]).text
        descriptions.push(description);
        enhancedDesc.push(this.userDataService.parseLocationForRuleDescription(description));
        icons.push('');
        statuses.push(0);
        devCapIds.push(rule.ifClause[1].device.id+','+rule.ifClause[1].capability.id);
      }

      // add the then clause
      words.push("then");
      rule.thenClause[0] = this.userDataService.getTextForClause(rule.thenClause[0]);
      description = rule.thenClause[0].text;
      descriptions.push(description);
      enhancedDesc.push(this.userDataService.parseLocationForRuleDescription(description));
      statuses.push(0);
      if (rule.thenClause[0].channel) {
        icons.push(rule.thenClause[0].channel.icon);
      } else {
        icons.push("");
      }
      devCapIds.push(rule.thenClause[0].device.id+','+rule.thenClause[0].capability.id);

      // add other while clauses
      if (rule.ifClause.length > 2) {
        for (let clause of rule.ifClause.slice(2)) {
          // placeholder
          words.push('');
          descriptions.push('');
          enhancedDesc.push([]);
          icons.push('');
          statuses.push(0);
          devCapIds.push(',');
          // the correct column
          words.push("and");
          description = this.userDataService.getTextForClause(clause).text
          descriptions.push(description);
          enhancedDesc.push(this.userDataService.parseLocationForRuleDescription(description));
          icons.push('');
          statuses.push(0);
          devCapIds.push(clause.device.id+','+clause.capability.id);
          // placeholder
          words.push('');
          descriptions.push('');
          enhancedDesc.push([]);
          icons.push('');
          statuses.push(0);
          devCapIds.push(',');
        }
      }

      const ruleRep: ChangedRuleUIRepresentation = {
        words: words,
        icons: icons,
        descriptions: descriptions,
        enhancedDesc: enhancedDesc,
        status: 0,
        statuses: statuses,
        devCapIds: devCapIds
      };
      const rulePair: ChangedRuleUIRepresentationPair = {
        left: JSON.parse(JSON.stringify(ruleRep)),
        right: JSON.parse(JSON.stringify(ruleRep))
      };
      return rulePair;
    };

    this.PROGRAM_TABLE = this.unparsedOrigRules.map((rule => ruleToRep(rule)));
    let cluster = this.patchClusters[this.currentCluster]
    if (cluster.mode == 'modify-rule') {
      // we should only have one patch within this cluster
      let patch = cluster.patches[0].patch;
      let rule_id = patch['rule_id'];
      if (patch['mode'] == 'add-condition') {
        let clause = patch['new_condition'];
        clause = this.userDataService.getTextForClause(clause);
        this.addConditionHelper(this.PROGRAM_TABLE[rule_id].right, clause);
        this.PROGRAM_TABLE[rule_id].right.status = 22;
        this.PROGRAM_TABLE[rule_id].left.status = 21;
      } else if (patch['mode'] == 'delete-condition') {
        // we should only have one patch within this cluster
        let cond_id = patch['condition_id'];
        let real_cond_id = 1 + cond_id * 3;
        this.PROGRAM_TABLE[rule_id].left.statuses[real_cond_id] = -1;
        this.deleteConditionHelper(this.PROGRAM_TABLE[rule_id].right, real_cond_id);
        this.PROGRAM_TABLE[rule_id].right.status = 22;
        this.PROGRAM_TABLE[rule_id].left.status = 21;
      } else if (patch['mode'] == 'modify-condition') {
        // we should only have one patch within this cluster
        // mark the original condition as deleted
        let cond_id = patch['condition_id'];
        let real_cond_id = 1 + cond_id * 3;
        let clause = patch['new_condition'];
        this.modifyConditionHelper(this.PROGRAM_TABLE[rule_id].right, real_cond_id, clause);
        this.PROGRAM_TABLE[rule_id].right.status = 22;
        this.PROGRAM_TABLE[rule_id].left.status = 21;
      } else {
        // TODO: support modifying triggers
        console.error("Patch mode not known:", patch['mode']);
      }
    } else if (cluster.mode == 'add-rule') {
      // we could have multiple patches here
      // now we should show the first one
      // TODO: what about others?
      let patch_mask = cluster.patches[0];
      let patch = patch_mask.patch;
      let rule = patch['new_rule'];
      let rulePair = ruleToRep(rule);
      this.PROGRAM_TABLE.push(rulePair);
      this.PROGRAM_TABLE[this.PROGRAM_TABLE.length-1].left.status = 101;
      this.PROGRAM_TABLE[this.PROGRAM_TABLE.length-1].right.status = 1;
    } else if (cluster.mode == 'delete-rule') {
      // we only have one patch within this cluster
      // let patch = cluster.patches[0].patch;
      // let rule_id = patch['rule_id'];
      // this.RULES[rule_id].modes = this.RULES[rule_id].modes.map(x => 1);
    } else {
      console.error("Patch cluster mode not known:", cluster.mode);
    }
  }

  private parseMetaDescription() {
    this.patchMetaDescriptions = [];
    this.patchMetaDescriptions.push('Regarding the action \"' + this.getCurrentCommandText() + '\", with this patch: ');
    if (this.rsiService.mode == 'sf' || this.rsiService.mode == 'nf') {
      this.patchMetaDescriptions.push(this.patchClusters[this.currentCluster].patches[0].patch.meta.FN_fixed + ' of proposed new actions would be automated.');
      this.patchMetaDescriptions.push(this.patchClusters[this.currentCluster].patches[0].patch.meta.FP_fixed + ' of the actions proposed to be cancelled would be cancelled.');
      this.patchMetaDescriptions.push(this.patchClusters[this.currentCluster].patches[0].patch.meta.TP_cancelled + ' of the automated actions not proposed to be cancelled  would be cancelled.');
      this.patchMetaDescriptions.push(this.patchClusters[this.currentCluster].patches[0].patch.meta.new_introduced + ' new automated actions would be introduced.');
    } else {
      this.patchMetaDescriptions.push(this.patchClusters[this.currentCluster].patches[0].patch.meta.FN_fixed + ' of your manual actions would be automated.');
      this.patchMetaDescriptions.push(this.patchClusters[this.currentCluster].patches[0].patch.meta.FP_fixed + ' of the automated actions reverted by you would be cancelled.');
      this.patchMetaDescriptions.push(this.patchClusters[this.currentCluster].patches[0].patch.meta.TP_cancelled + ' of the automated actions not reverted by you would be cancelled.');
      this.patchMetaDescriptions.push(this.patchClusters[this.currentCluster].patches[0].patch.meta.new_introduced + ' new automated actions would be introduced.');
    }
  }

  parseDevCapMeta(metaDict) {
    for (let devCap in metaDict) {
      this.devCapMetas[devCap] = 'Max: ' + metaDict[devCap].max + ' at ' + metaDict[devCap].max_time + '\n' + 
                                 'Min: ' + metaDict[devCap].min + ' at ' + metaDict[devCap].min_time;
    }
  }

  gotoPrev() {
    this.currentCluster = this.currentCluster == 0 ? this.currentCluster : this.currentCluster-1;
    this.parseCluster();
    if (!this.isAlt)
      this.createVis();
  }

  gotoNext() {
    this.currentCluster = this.currentCluster+1<this.clusterNum ? this.currentCluster+1 : this.currentCluster;
    this.parseCluster();
    if (!this.isAlt)
      this.createVis();
  }

  public getCurrentCommandText() {
    return this.userDataService.getTextFromParVal(this.rsiService.currentDevice, 
                                                  this.rsiService.currentCommand.capability, 
                                                  [this.rsiService.currentCommand.parameter], 
                                                  [{"value": this.rsiService.currentCommand.value,
                                                    "comparator": "="}]);
  }

  showOrHideAlt() {
    this.showAlternatives = !this.showAlternatives;
  }

  fetchLog() {
    this.logFetched = false;
    let self = this;
    this.rsiService.fetchLogForVis(this.vis_token).subscribe(data => {
      self.traceLogsFN = data["fn_vis_list"];
      self.traceLogsTEC = data["tec_vis_list"];
      self.traceLogsNI = data["ni_vis_list"];
      self.devList = data["dev_list"];
      self.capList = data["cap_list"];

      self.ruleMasksFN = data["masks_fn"];
      self.ruleMasksTEC = data["masks_tec"];
      self.ruleMasksNI = data["masks_ni"];
      // self.tapLogsShownPositive = data["tap_clips_shown_positive"];
      // self.tapLogsShownNegative = data["tap_clips_shown_negative"];
      self.targetId = data["target_id"];
      self.tapSensorList = data["rule_sensor_list"];
      self.nRevert = data["n_revert"];
      self.refVis = self.createVis();
      self.logFetched = true;
    });
  }

  // creating visualization for a certain patch
  createVis() {
    this.entry.clear();
    const factory = this.resolver.resolveComponentFactory(VisComponent);
    const componentRef = this.entry.createComponent(factory);
    componentRef.instance.traceLogsFN = this.traceLogsFN;
    componentRef.instance.traceLogsTEC = this.traceLogsTEC;
    componentRef.instance.traceLogsNI = this.traceLogsNI;

    componentRef.instance.maskFN = this.ruleMasksFN[this.currentCluster];
    componentRef.instance.maskTEC = this.ruleMasksTEC[this.currentCluster];
    componentRef.instance.maskNI = this.ruleMasksNI[this.currentCluster];
    componentRef.instance.currentCluster = this.currentCluster;
    componentRef.instance.mode = this.rsiService.mode == 'sf' || this.rsiService.mode == 'nf';
    componentRef.instance.devList = this.devList;
    componentRef.instance.capList = this.capList;
    componentRef.instance.tapLogsShownPositive = [];
    componentRef.instance.tapLogsShownNegative = [];
    componentRef.instance.targetId = this.targetId;
    componentRef.instance.tapSensorList = this.tapSensorList;
    componentRef.instance.currentCommandText = this.getCurrentCommandText();
    componentRef.instance.nRevert = this.nRevert;
    
    // Put patch meta into the visualization component
    // Each entry includes FP_fixed, FN_fixed, TP_cancelled, new_introduced
    componentRef.instance.patchMeta = this.patchClusters[this.currentCluster].patches[0].patch.meta;

    return componentRef;
  }

  checkAlternative() {
    this.route.routeReuseStrategy.shouldReuseRoute = () => false;
    this.route.onSameUrlNavigation = 'reload';
    this.route.navigate(['/result', { alt: true }]);
  }
}

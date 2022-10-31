import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { CommonModule } from '@angular/common';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatSliderModule } from '@angular/material/slider';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card'
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatListModule } from '@angular/material/list';
import { MatBottomSheetModule } from '@angular/material/bottom-sheet';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { FormsModule } from '@angular/forms';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatTreeModule } from '@angular/material/tree';
import { MatDialogModule } from '@angular/material/dialog';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatMenuModule } from '@angular/material/menu';
import { MatRadioModule } from '@angular/material/radio';

import { DashboardComponent } from './dashboard/dashboard.component';
// import { RsibaseComponent } from './rsibase/rsibase.component';
import { VisComponent } from './vis/vis.component';
import { ModeselComponent } from './modesel/modesel.component';
// import { RsibasedComponent } from './rsibased/rsibased.component';
import { StatusComponent } from './vis/status/status.component';
import { CurrentruleComponent } from './currentrule/currentrule.component';
import { LegendComponent } from './vis/legend/legend.component';
import { VisbaseComponent } from './vis/visbase/visbase.component';
import { ZoneselComponent } from './zonesel/zonesel.component';
import { DevselComponent } from './devsel/devsel.component';
import { RsibasefComponent } from './rsibasef/rsibasef.component';
import { FeedbackComponent } from './vis/feedback/feedback.component';
import { FbrltComponent } from './result/fbrlt.component';
import { RsibasesComponent, ModifyWordsPipe } from './rsibases/rsibases.component';
import { SyntaxfbComponent } from './rsibases/syntaxfb/syntaxfb.component';
import { ChoicesComponent } from './choices/choices.component';

const routes: Routes = [
  // {
  //   path: 'synthesize',
  //   component: RsibaseComponent
  // },
  {
    path: 'synthesize/zonesel',
    component: ZoneselComponent
  },
  {
    path: 'synthesize/devsel',
    component: DevselComponent
  },
  {
    path: 'synthesize/dashboard',
    component: DashboardComponent
  },
  // {
  //   path: 'synthesize/visualization',
  //   component: VisComponent
  // },
  // {
  //   path: 'debug',
  //   component: RsibasedComponent
  // },
  {
    path: 'manualfeedback',
    component: RsibasefComponent
  },
  {
    path: 'result',
    component: FbrltComponent
  },
  {
    path: 'syntaxfeedback',
    component: RsibasesComponent
  },
  {
    path: 'choices',
    component: ChoicesComponent
  }

]

@NgModule({
  declarations: [DashboardComponent, VisComponent, ModeselComponent, StatusComponent, CurrentruleComponent, LegendComponent, VisbaseComponent, ZoneselComponent, DevselComponent, RsibasefComponent, FeedbackComponent, FbrltComponent, RsibasesComponent, SyntaxfbComponent, ModifyWordsPipe, ChoicesComponent],
  imports: [
    RouterModule.forChild(routes),
    CommonModule, FormsModule,
    MatSelectModule, MatSliderModule, MatButtonModule, MatIconModule, MatTreeModule,
    BrowserAnimationsModule, MatFormFieldModule, MatCardModule, MatSidenavModule,
    MatListModule, MatProgressSpinnerModule, MatBottomSheetModule, MatTooltipModule,
    MatDialogModule, MatExpansionModule, MatMenuModule, MatRadioModule
  ],
  exports: [
    VisbaseComponent,
    VisComponent
  ],
  entryComponents: [
    ModeselComponent,
    CurrentruleComponent,
    LegendComponent,
    VisbaseComponent,
    VisComponent,
    FeedbackComponent,
    SyntaxfbComponent
  ],
})
export class RsiModule { }

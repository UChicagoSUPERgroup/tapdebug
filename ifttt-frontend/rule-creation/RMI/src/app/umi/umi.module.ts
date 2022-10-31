import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule } from '@angular/forms';

import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material';
import { MatTabsModule } from '@angular/material/tabs';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatListModule } from '@angular/material/list';
import { MatSelectModule } from '@angular/material/select';
import { MatStepperModule } from '@angular/material/stepper';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatRadioModule } from '@angular/material/radio';

import { UmibaseComponent } from './umibase/umibase.component';
import { LoginComponent } from './login/login.component';
import { AdminComponent } from './admin/admin.component';
import { MonitorComponent } from './monitor/monitor.component';

const routes: Routes = [
  {
    path: '',
    component: UmibaseComponent,
    children: [
        {
            path: '',
            component: LoginComponent
        },
        {
            path: 'admin',
            component: AdminComponent
        },
        {
            path: 'monitor',
            component: MonitorComponent
        }
    ]
  }
]

@NgModule({
  imports: [
    RouterModule.forChild(routes),
    CommonModule, MatIconModule, MatButtonModule, MatProgressSpinnerModule,
    MatCardModule, MatFormFieldModule, MatInputModule, MatRadioModule,
    MatTabsModule, MatSlideToggleModule, MatSidenavModule,
    MatListModule, MatSelectModule, MatStepperModule, ReactiveFormsModule
  ],
  declarations: [
      UmibaseComponent, LoginComponent, AdminComponent, MonitorComponent
  ],
  exports: [
    RouterModule
  ]
})
export class UmiModule { }

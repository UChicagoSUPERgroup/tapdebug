import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { ZoneselComponent } from './zonesel.component';

describe('ZoneselComponent', () => {
  let component: ZoneselComponent;
  let fixture: ComponentFixture<ZoneselComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ ZoneselComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(ZoneselComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

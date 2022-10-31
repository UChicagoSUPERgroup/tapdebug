import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { DevselComponent } from './devsel.component';

describe('DevselComponent', () => {
  let component: DevselComponent;
  let fixture: ComponentFixture<DevselComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ DevselComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(DevselComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

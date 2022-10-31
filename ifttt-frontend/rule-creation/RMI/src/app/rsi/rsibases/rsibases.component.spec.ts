import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { RsibasesComponent } from './rsibases.component';

describe('RsibasesComponent', () => {
  let component: RsibasesComponent;
  let fixture: ComponentFixture<RsibasesComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ RsibasesComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(RsibasesComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

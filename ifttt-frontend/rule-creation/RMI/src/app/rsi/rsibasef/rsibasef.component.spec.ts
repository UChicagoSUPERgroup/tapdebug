import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { RsibasefComponent } from './rsibasef.component';

describe('RsibasefComponent', () => {
  let component: RsibasefComponent;
  let fixture: ComponentFixture<RsibasefComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ RsibasefComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(RsibasefComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

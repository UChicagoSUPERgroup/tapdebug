import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { SyntaxfbComponent } from './syntaxfb.component';

describe('SyntaxfbComponent', () => {
  let component: SyntaxfbComponent;
  let fixture: ComponentFixture<SyntaxfbComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ SyntaxfbComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(SyntaxfbComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

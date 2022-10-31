import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { FbrltComponent } from './fbrlt.component';

describe('FbrltComponent', () => {
  let component: FbrltComponent;
  let fixture: ComponentFixture<FbrltComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ FbrltComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(FbrltComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

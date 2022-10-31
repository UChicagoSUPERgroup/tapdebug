import { TestBed, inject } from '@angular/core/testing';

import { RsiService } from './rsi.service';

describe('RsiService', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [RsiService]
    });
  });

  it('should be created', inject([RsiService], (service: RsiService) => {
    expect(service).toBeTruthy();
  }));
});

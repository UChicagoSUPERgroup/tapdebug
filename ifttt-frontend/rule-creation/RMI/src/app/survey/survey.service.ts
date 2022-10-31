import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams, HttpErrorResponse } from '@angular/common/http';

import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class SurveyService {

  constructor(private http: HttpClient) { }

  private apiUrl: string = environment.apiUrl;

  public parseText(rawText: string) {
    // this doesn't support nested entries like <rule><it></it></rule>
    let result = [];
    let i = 0; // current location
    let start_i = 0; // everything before start_i has been parsed
    let current_label = "";
    while (i < rawText.length) {
      while (rawText.charAt(i) != '<' && i < rawText.length)
        i = i+1;
      result.push([current_label, rawText.substring(start_i, i)]);
      start_i = i;
      if (rawText.charAt(i) == "<") {
        let end_index = rawText.indexOf(">", i)
        if (rawText.charAt(i+1) == "/") {
          current_label = "";
        } else {
          current_label = rawText.substring(i+1, end_index);
        }
        start_i = end_index + 1;
        i = end_index + 1;
      }
    }
    return result;
  }

  public getScenarioInfo(usercode: string, stage: string, taskid: number) {
    let url = this.apiUrl + 'user/getscenarioinfo/';
    let body = {'usercode': usercode, 'stage': stage, 'taskid': taskid};
    return this.http.post(url, body, {
      headers: new HttpHeaders().set('Content-Type', 'application/json'),
    });
  }

  public uploadTrace(locId) {
    let url = this.apiUrl + 'user/upload_trace/';
    let body = {'loc_id': locId};
    return this.http.post(url, body, {
      headers: new HttpHeaders().set('Content-Type', 'application/json'),
    });
  }
  
}

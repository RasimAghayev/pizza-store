import { Component, input } from '@angular/core';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

@Component({
  imports: [MatProgressSpinnerModule],
  selector: 'lib-loading',
  styleUrl: './loading.css',
  templateUrl: './loading.html',
})
export class Loading {
  message = input('Loading…');
  diameter = input(48);
}

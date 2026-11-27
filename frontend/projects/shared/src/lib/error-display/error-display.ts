import { Component, input, output } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';

@Component({
  imports: [MatButtonModule],
  selector: 'lib-error-display',
  styleUrl: './error-display.css',
  templateUrl: './error-display.html',
})
export class ErrorDisplay {
  title = input('Something went wrong');
  message = input.required<string>();
  dismissible = input(false);
  dismissed = output<void>();
}

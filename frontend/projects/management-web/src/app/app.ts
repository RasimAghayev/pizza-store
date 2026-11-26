import { Component, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
// calls into shared/src/lib/app-shell/app-shell.ts -- AppShell
import { AppShell } from 'shared';

@Component({
  imports: [RouterOutlet, AppShell],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App {
  protected readonly title = signal('management-web');
}

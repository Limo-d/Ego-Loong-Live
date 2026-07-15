export class Navigation {
  constructor(onChange) {
    this.current = 'overview'; this.onChange = onChange;
    document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => this.show(button.dataset.view)));
  }
  show(name) {
    this.current = name;
    document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view.id === `view-${name}`));
    document.querySelectorAll('[data-view]').forEach(button => button.classList.toggle('active', button.dataset.view === name));
    this.onChange?.(name);
  }
}


export class LiveSocket {
  constructor(url, handlers = {}) {
    this.url = url; this.handlers = handlers; this.ws = null; this.closed = false; this.retry = 500; this.timer = null;
  }
  connect() {
    if (this.closed) return;
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
    const url = this.url || `${scheme}://${location.host}/ws`;
    this.handlers.state?.('connecting');
    this.ws = new WebSocket(url);
    this.ws.onopen = () => { this.retry = 500; this.handlers.state?.('open'); this.ping(); };
    this.ws.onmessage = event => { try { this.handlers.message?.(JSON.parse(event.data)); } catch (error) { console.warn('WS payload', error); } };
    this.ws.onerror = () => this.ws?.close();
    this.ws.onclose = () => { this.handlers.state?.('closed'); if (!this.closed) { clearTimeout(this.timer); this.timer = setTimeout(() => this.connect(), this.retry); this.retry = Math.min(8000, this.retry * 1.7); } };
  }
  ping() { if (this.ws?.readyState === WebSocket.OPEN) this.ws.send('ping'); clearTimeout(this.timer); if (!this.closed) this.timer = setTimeout(() => this.ping(), 15000); }
  close() { this.closed = true; clearTimeout(this.timer); this.ws?.close(); }
}


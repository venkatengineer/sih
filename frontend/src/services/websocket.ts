export type WebSocketHandler = (msg: any) => void;

class WebSocketClient {
  private ws: WebSocket | null = null;
  private handlers: Set<WebSocketHandler> = new Set();
  private reconnectTimer: number | null = null;

  connect() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return;

    const loc = window.location;
    const proto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = loc.host.includes(':3000') ? 'localhost:8000' : loc.host;
    const url = `${proto}//${host}/ws`;

    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log('[Control Center] Connected to backend WebSocket');
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handlers.forEach((h) => h(data));
        } catch (e) {
          console.error('[Control Center] WS parse error:', e);
        }
      };

      this.ws.onclose = () => {
        this.ws = null;
        if (!this.reconnectTimer) {
          this.reconnectTimer = window.setTimeout(() => {
            this.reconnectTimer = null;
            this.connect();
          }, 2000);
        }
      };
    } catch (e) {
      console.error('[Control Center] Connection failed:', e);
    }
  }

  subscribe(handler: WebSocketHandler) {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }
}

export const wsClient = new WebSocketClient();

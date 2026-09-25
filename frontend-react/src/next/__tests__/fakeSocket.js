// A WebSocket stand-in: tests push server messages and read what the client sent.
export function fakeSocketFactory() {
  const sockets = []
  class FakeSocket {
    constructor(url) { this.url = url; this.sent = []; this.readyState = 0; this.closedWith = null; sockets.push(this) }
    send(text) { this.sent.push(JSON.parse(text)) }
    close(code = 1000) { if (this.readyState === 3) return; this.readyState = 3; this.closedWith = code; this.onclose?.({ code }) }
    // test helpers
    open() { this.readyState = 1; this.onopen?.({}) }
    receive(message) { this.onmessage?.({ data: JSON.stringify(message) }) }
    serverClose(code = 1006) { this.readyState = 3; this.onclose?.({ code }) }
    fail() { this.onerror?.({}); this.serverClose(1006) }
    commands() { return this.sent.map(message => message.command) }
  }
  return { FakeSocket, sockets }
}

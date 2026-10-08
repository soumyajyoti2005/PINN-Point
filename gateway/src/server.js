import { createServer } from 'http';
import { URL } from 'url';
import { WebSocketServer } from 'ws';

export function createGateway(config, deps = {}) {
  const server = createServer((req, res) => {
    if (req.method === 'GET' && req.url === '/healthz') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ok' }));
    } else {
      res.writeHead(404);
      res.end();
    }
  });

  const wss = new WebSocketServer({ noServer: true });

  server.on('upgrade', (request, socket, head) => {
    try {
      const url = new URL(request.url, `http://${request.headers.host}`);
      if (url.pathname !== '/ws') {
        socket.write('HTTP/1.1 404 Not Found\r\n\r\n');
        socket.destroy();
        return;
      }
      if (url.searchParams.get('token') !== config.wsToken) {
        socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
        socket.destroy();
        return;
      }
      wss.handleUpgrade(request, socket, head, (ws) => {
        wss.emit('connection', ws, request);
      });
    } catch (err) {
      socket.destroy();
    }
  });

  wss.on('connection', (ws) => {
    ws.isAlive = true;
    ws.on('pong', () => {
      ws.isAlive = true;
    });
  });

  const interval = setInterval(() => {
    wss.clients.forEach((ws) => {
      if (ws.isAlive === false) return ws.terminate();
      ws.isAlive = false;
      ws.ping();
    });
  }, 30000);

  const broadcast = (dataStr) => {
    wss.clients.forEach((client) => {
      if (client.readyState === 1) { // OPEN
        client.send(dataStr);
      }
    });
  };

  const close = (callback) => {
    clearInterval(interval);
    wss.clients.forEach((ws) => ws.terminate());
    wss.close(() => {
      server.close(callback);
    });
  };

  return { server, broadcast, close };
}

import test from 'node:test';
import assert from 'node:assert';
import { createGateway } from '../src/server.js';
import WebSocket from 'ws';

test('Gateway Server', async (t) => {
  const config = { wsToken: 't' };
  const { server, broadcast, close } = createGateway(config);
  
  await new Promise(resolve => server.listen(0, resolve));
  const port = server.address().port;

  await t.test('GET /healthz returns 200', async () => {
    const res = await fetch(`http://localhost:${port}/healthz`);
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.deepStrictEqual(body, { status: 'ok' });
  });

  await t.test('WS connection with missing/wrong token is rejected', async () => {
    const ws1 = new WebSocket(`ws://localhost:${port}/ws`);
    await new Promise(resolve => {
      ws1.on('unexpected-response', (req, res) => {
        assert.strictEqual(res.statusCode, 401);
        resolve();
      });
    });

    const ws2 = new WebSocket(`ws://localhost:${port}/ws?token=wrong`);
    await new Promise(resolve => {
      ws2.on('unexpected-response', (req, res) => {
        assert.strictEqual(res.statusCode, 401);
        resolve();
      });
    });
  });

  await t.test('WS connection to wrong path is rejected', async () => {
    const ws = new WebSocket(`ws://localhost:${port}/wrong?token=t`);
    await new Promise(resolve => {
      ws.on('unexpected-response', (req, res) => {
        assert.strictEqual(res.statusCode, 404);
        resolve();
      });
    });
  });

  await t.test('WS connection with right token connects and receives broadcast', async () => {
    const ws = new WebSocket(`ws://localhost:${port}/ws?token=t`);
    
    await new Promise(resolve => {
      ws.on('open', resolve);
    });

    const msgPromise = new Promise(resolve => {
      ws.on('message', (data) => resolve(data.toString()));
    });

    broadcast('{"hello":"world"}');
    
    const msg = await msgPromise;
    assert.strictEqual(msg, '{"hello":"world"}');
    ws.close();
  });

  // Ensure server closes
  await new Promise(resolve => close(resolve));
});

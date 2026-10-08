import { createClient } from 'redis';
import { loadConfig } from './config.js';
import { createGateway } from './server.js';
import { validateEvent } from './validate.js';

function log(level, message, extra = {}) {
  console.log(JSON.stringify({ level, message, ...extra }));
}

async function main() {
  const config = loadConfig();

  const { server, broadcast, close } = createGateway(config);

  const redisClient = createClient({ url: config.redisUrl });
  const redisSubscriber = redisClient.duplicate();

  redisClient.on('error', (err) => log('error', 'Redis Client Error', { error: err.message }));
  redisSubscriber.on('error', (err) => log('error', 'Redis Subscriber Error', { error: err.message }));

  await redisClient.connect();
  await redisSubscriber.connect();

  await redisSubscriber.subscribe(config.redisChannel, (message) => {
    try {
      const obj = JSON.parse(message);
      const val = validateEvent(obj);
      if (val.ok) {
        broadcast(message);
      } else {
        log('warn', 'Invalid event dropped', { reason: val.error });
      }
    } catch (e) {
      log('error', 'Failed to parse message', { error: e.message });
    }
  });

  server.listen(config.port, '0.0.0.0', () => {
    log('info', `Gateway listening on 0.0.0.0:${config.port}`);
  });

  const shutdown = async () => {
    log('info', 'Shutting down...');
    close(async () => {
      await redisSubscriber.unsubscribe(config.redisChannel);
      await redisSubscriber.quit();
      await redisClient.quit();
      process.exit(0);
    });
  };

  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}

main().catch((err) => {
  log('error', 'Fatal error', { error: err.message });
  process.exit(1);
});

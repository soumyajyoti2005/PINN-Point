import WebSocket from 'ws';
import { createClient } from 'redis';
import fs from 'fs';
import path from 'path';

async function run() {
  const wsToken = process.env.WS_TOKEN;
  const port = process.env.GATEWAY_PORT;
  const redisHost = process.env.REDIS_HOST;
  const redisPort = process.env.REDIS_PORT;
  const redisChannel = process.env.REDIS_CHANNEL;
  const contractsDir = process.env.CONTRACTS_DIR;

  if (!wsToken || !port || !redisHost || !redisPort || !redisChannel || !contractsDir) {
    console.error('Missing required environment variables.');
    process.exit(1);
  }

  const receivedMessages = [];
  
  // 1. Connect good client
  const goodWs = new WebSocket(`ws://127.0.0.1:${port}/ws?token=${wsToken}`);
  await new Promise((resolve, reject) => {
    goodWs.on('open', resolve);
    goodWs.on('error', reject);
  });
  console.log('PASS: Connected good ws client');
  
  goodWs.on('message', (data) => {
    receivedMessages.push(data.toString());
  });

  // 2. Connect bad client
  const badWs = new WebSocket(`ws://127.0.0.1:${port}/ws?token=wrong`);
  await new Promise((resolve) => {
    badWs.on('unexpected-response', (req, res) => {
      if (res.statusCode === 401) {
        console.log('PASS: Bad token connection rejected with 401');
        resolve();
      }
    });
  });

  // 3. Publish to Redis
  const redisClient = createClient({ url: `redis://${redisHost}:${redisPort}` });
  await redisClient.connect();
  
  const invalidJson = fs.readFileSync(path.join(contractsDir, 'examples', 'event_level_update_invalid.json'), 'utf8');
  const validJson = fs.readFileSync(path.join(contractsDir, 'examples', 'event_level_update_valid.json'), 'utf8');
  const validDetectionJson = fs.readFileSync(path.join(contractsDir, 'examples', 'event_detection_valid.json'), 'utf8');

  await redisClient.publish(redisChannel, invalidJson);
  await redisClient.publish(redisChannel, validJson);
  await redisClient.publish(redisChannel, validDetectionJson);
  console.log('PASS: Published valid and invalid payloads to redis');

  // 4. Expect exactly 2 messages
  await new Promise(r => setTimeout(r, 2000));
  
  goodWs.close();
  await redisClient.quit();

  if (receivedMessages.length === 2) {
    const m1 = JSON.parse(receivedMessages[0]);
    const m2 = JSON.parse(receivedMessages[1]);
    
    if (m1.type === 'level_update' && m2.type === 'detection') {
      console.log('PASS: Received exactly the two valid messages in order');
      process.exit(0);
    } else {
      console.error(`FAIL: Messages did not match expected types. Got ${m1.type} and ${m2.type}`);
      process.exit(1);
    }
  } else {
    console.error(`FAIL: Expected 2 messages, got ${receivedMessages.length}`);
    process.exit(1);
  }
}

run().catch(err => {
  console.error('FAIL: Unexpected error', err);
  process.exit(1);
});

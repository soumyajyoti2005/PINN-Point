export function loadConfig() {
  const required = [
    'REDIS_HOST',
    'REDIS_PORT',
    'REDIS_CHANNEL',
    'GATEWAY_PORT',
    'WS_TOKEN'
  ];

  for (const req of required) {
    if (!process.env[req]) {
      console.error(`Missing required environment variable: ${req}`);
      process.exit(1);
    }
  }

  const redisHost = process.env.REDIS_HOST;
  const redisPort = parseInt(process.env.REDIS_PORT, 10);
  
  return {
    redisUrl: `redis://${redisHost}:${redisPort}`,
    redisChannel: process.env.REDIS_CHANNEL,
    port: parseInt(process.env.GATEWAY_PORT, 10),
    wsToken: process.env.WS_TOKEN,
    contractsDir: process.env.CONTRACTS_DIR
  };
}

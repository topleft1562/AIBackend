import express from 'express';
import dotenv from 'dotenv';
import { createServer } from 'http';

dotenv.config({ path: `.env.${process.env.NODE_ENV || 'development'}` });

const app = express();
const server = createServer(app);
const PORT = process.env.PORT || 3000;

// Basic health check
app.get('/', (_, res) => {
  res.send('🚀 Fat Cat Query Engine is online!');
});

// Graceful shutdown handler
async function gracefulShutdown(signal: string) {
  console.log(`🔌 Received ${signal}. Shutting down...`);

  await new Promise<void>((resolve) => {
    server.close(() => {
      console.log('✅ HTTP server closed');
      resolve();
    });
  });

  process.exit(0);
}

// Listen for shutdown signals
['SIGINT', 'SIGTERM'].forEach(signal => {
  process.on(signal, () => gracefulShutdown(signal));
});

// Start server
server.listen(PORT, () => {
  console.log(`✅ Server running on port ${PORT}`);
});

export default server;

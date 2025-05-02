import express from 'express';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

app.get('/', (_, res) => {
  res.send('🚀 Fat Cat Query Engine is running!');
});

app.listen(PORT, () => {
  console.log(`✅ Server is listening on port ${PORT}`);
});


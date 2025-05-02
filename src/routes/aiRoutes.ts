import express from 'express';
import { getQueryEngine2 } from '../utils/queryEngine2.js';

const router = express.Router();

router.post('/ask', async (req, res) => {
  const { question } = req.body;
  if (!question) return res.status(400).json({ error: 'Question required' });

  const engine = getQueryEngine2();
  const response = await engine.chat({ message: question });
  res.json({ response: response?.response });
});

export default router;
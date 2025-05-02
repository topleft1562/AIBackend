import express from 'express';
import { getQueryEngine2 } from '../utils/queryEngine2';

const router = express.Router();

router.post('/response', async (req, res) => {
  try {
    const { message } = req.body;
    if (!message) return res.status(400).json({ error: 'Missing message' });

    const engine = getQueryEngine2();
    if (!engine) return res.status(500).json({ error: 'Query engine not ready' });

    const response = await engine.chat({ message });
    res.json({ reply: response.response });
  } catch (err) {
    console.error('❌ Error in /response:', err);
    res.status(500).json({ error: 'Failed to get response' });
  }
});

export default router;

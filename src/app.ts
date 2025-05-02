// src/app.ts
import express from 'express';
import aiRoutes from './aiRoutes';

const app = express();
app.use(express.json());
app.use('/ai', aiRoutes);

export default app;

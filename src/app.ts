import express from "express";
import "dotenv-flow/config";
import bodyParser from "body-parser";
import cors from "cors";
import helmet from "helmet";
import { sanitize } from "isomorphic-dompurify";
import rateLimit from "express-rate-limit";
import corsConfig from "./config/cors";
import aiRoutes from "./routes/aiRoutes";
import { OpenAI } from "openai";

const app = express();

app.set("trust proxy", 1);

// Security Middleware
app.use(helmet());

// Sanitize input
app.use((req, res, next) => {
  if (req.body) req.body = JSON.parse(sanitize(JSON.stringify(req.body)));
  if (req.query) req.query = JSON.parse(sanitize(JSON.stringify(req.query)));
  if (req.params) req.params = JSON.parse(sanitize(JSON.stringify(req.params)));
  next();
});

// CORS
app.use(cors(corsConfig));
app.options("*", cors(corsConfig));

// Rate Limiting
const limiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: 1000,
  message: "Too many requests from this IP, please try again later.",
  standardHeaders: true,
  legacyHeaders: false,
});
app.use(limiter);

// Body Parsers
app.use(bodyParser.json({ limit: "10mb" }));
app.use(bodyParser.urlencoded({ extended: true, limit: "10mb" }));

// Hide Express Signature
app.disable("x-powered-by");

// OpenAI instance
export const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

// Routes
app.use("/ai", aiRoutes);

// Error Handler
app.use((err: Error, req: express.Request, res: express.Response, _next: express.NextFunction) => {
  console.error("Unhandled Error:", err);
  res.status(500).json({
    error: "Internal Server Error",
    message: err.message,
  });
});

export default app;

);

export default app;

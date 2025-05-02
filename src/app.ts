import express from "express";
import "dotenv-flow/config";
import bodyParser from "body-parser";
import cors from "cors";
import helmet from "helmet";
import { sanitize } from "isomorphic-dompurify"; // Replaces xss-clean
import rateLimit from "express-rate-limit";
import { init } from "./db/dbConncetion";
import { logger } from "./sockets/logger";
import corsConfig from "./config/cors";
import aiRoutes from "./routes/aiRoutes"
import { OpenAI } from 'openai'



const app = express();

app.set("trust proxy", 1); // or "true"

// Security Middleware
app.use(helmet()); // Secure HTTP headers

// Middleware to sanitize incoming requests (Replaces xss-clean)
app.use((req, res, next) => {
  if (req.body) req.body = JSON.parse(sanitize(JSON.stringify(req.body)));
  if (req.query) req.query = JSON.parse(sanitize(JSON.stringify(req.query)));
  if (req.params) req.params = JSON.parse(sanitize(JSON.stringify(req.params)));
  next();
});

app.use(cors(corsConfig));
app.options("*", cors(corsConfig)); // Enable pre-flight requests


const limiter = rateLimit({
  windowMs: 1 * 60 * 1000, // 1 minutes
  max: 1000, // Limit each IP to 100 requests per `windowMs`
  message: "Too many requests from this IP, please try again later.",
  standardHeaders: true,
  legacyHeaders: false,
});

// Apply rate limiting to all routes
app.use(limiter);

// Body parser with security limits
app.use(bodyParser.json({ limit: "10mb" }));
app.use(bodyParser.urlencoded({ extended: true, limit: "10mb" }));

// Hide Express signature
app.disable("x-powered-by");

export const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
})

// Initialize database
(async () => {
  try {
    await init();
  } catch (error) {
    logger.error("Failed to initialize database:", error);
  }
})();

// Routes
app.use("/ai", aiRoutes);



// Error handling middleware
app.use(
  (err: Error, req: express.Request, res: express.Response, next: express.NextFunction) => {
    logger.error("Error:", err);
    res.status(500).json({
      error: "Internal Server Error",
      message: err.message,
    });
  }
);

export default app;

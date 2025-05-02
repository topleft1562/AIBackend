interface CorsConfig {
  origin: (origin: string | undefined, callback: (err: Error | null, allow?: boolean) => void) => void;
  methods: string[];
  credentials: boolean;
  allowedHeaders: string[];
}

const allowedOrigins: string[] = [
  "https://socialbot-production-c144.up.railway.app",
];

const isDev = process.env.NODE_ENV === "development";

const corsConfig: CorsConfig = {
  origin: (origin, callback) => {
    if (
      isDev ||              // Don't block anything in dev mode
      !origin ||            // Allow same-origin or curl/Postman
      allowedOrigins.includes(origin)
    ) {
      callback(null, true);
    } else {
      callback(new Error("Not allowed by CORS"));
    }
  },
  methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
  credentials: true,
  allowedHeaders: ["Content-Type", "Authorization", "x-api-key"],
};

export default corsConfig;

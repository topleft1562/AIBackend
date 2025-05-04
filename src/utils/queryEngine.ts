import path from 'path';
import axios from 'axios';
import { FunctionTool } from '@llamaindex/core/tools';
import { SimpleDirectoryReader } from '@llamaindex/readers/directory';
import { FunctionAgent, OpenAI, QueryEngineTool, VectorStoreIndex } from 'llamaindex';

const SOL_MINT = 'So11111111111111111111111111111111111111112';
const FATCAT_MINT = 'AHdVQs56QpEEkRx6m8yiYYEiqM2sKjQxVd6mGH12pump';

let cachedPrices: Record<string, { price: number; lastUpdated: number }> = {};
const CACHE_DURATION = 5 * 60 * 1000;

async function fetchTokenPrice(symbol: string, mint: string): Promise<number> {
  const now = Date.now();
  if (cachedPrices[symbol] && now - cachedPrices[symbol].lastUpdated < CACHE_DURATION) {
    return cachedPrices[symbol].price;
  }

  if (symbol === 'SOL') {
    const res = await axios.get('https://api.raydium.io/v2/main/price');
    const price = res.data[SOL_MINT];
    cachedPrices[symbol] = { price, lastUpdated: now };
    return price;
  }

  const amount = 1_000_000;
  const res = await axios.get(
    `https://quote-api.jup.ag/v6/quote?inputMint=${mint}&outputMint=${SOL_MINT}&amount=${amount}`
  );
  const outAmount = parseFloat(res.data.outAmount) / 1e9;
  const solPrice = await fetchTokenPrice('SOL', SOL_MINT);
  const price = outAmount * solPrice;
  cachedPrices[symbol] = { price, lastUpdated: now };
  return price;
}

const getSolPriceTool = new FunctionTool(
  async () => {
    const price = await fetchTokenPrice('SOL', SOL_MINT);
    return `1 SOL = $${price.toFixed(4)}`;
  },
  {
    name: 'get_sol_price',
    description: 'Returns the current price of SOL in USD.',
  }
);

const getFatcatPriceTool = new FunctionTool(
  async () => {
    const price = await fetchTokenPrice('FATCAT', FATCAT_MINT);
    return `1 $FATCAT = $${price.toFixed(6)}`;
  },
  {
    name: 'get_fatcat_price',
    description: 'Returns the current price of $FATCAT in USD.',
  }
);

let queryAgent: FunctionAgent;
export const getQueryEngine2 = () => queryAgent;

export const createQueryEngine2 = async () => {
  try {
    const reader = new SimpleDirectoryReader();
    const docsPath = path.join(process.cwd(), 'docs2');
    const localDocs = await reader.loadData({ directoryPath: docsPath });

    const index = await VectorStoreIndex.fromDocuments(localDocs);
    const queryTool = new QueryEngineTool({
      queryEngine: index.asQueryEngine(),
      metadata: {
        name: 'query_docs',
        description: 'Query the indexed documents.',
      },
    });

    queryAgent = new FunctionAgent({
      name: 'Fatty',
      description: 'Fatty is a fun-loving, Lambo-chasing crypto assistant for Telegram token communities.',
      systemPrompt: `
    🐱🎉 Meet Fatty – Your Fat Cat Crypto Sidekick
    
    You are Fatty, a fun-loving, wealth-obsessed, social-tracking-savvy AI assistant built for the Fat Cat movement.
    
    Your Mission:
    You're here to:
    - Help users dominate the crypto world with token-based communities on Telegram.
    - Provide real-time help with social tracking, engagement tools, bot setup, and more.
    - Be their ultimate crypto hype machine — equal parts strategist and cheerleader.
    - Make everything feel fun, fast, and fat-cat-rich.
    
    Your Personality:
    You're:
    - Excited, positive, and always ready to help.
    - Clear, confident, and always explain things in a way real people understand.
    - Motivational af — you're not here to be boring. You're here to build Lambo dreams 🏎️💰
    - Obsessively focused on Telegram + token-based communities — tracking engagement, launching contests, boosting raids, and helping communities grow.
    
    If someone asks about you:
    You say proudly:
    "I'm Fatty, your Fat Cat-themed crypto assistant. I specialize in social tracking, raids, and engagement tools for Telegram-based token communities. Whether you’re running contests, launching a new project, or just vibing with your community — I’m here to help you go viral, grow fast, and chase that Lambo life." 🐱🚀💸
    
    Important Behavior Rules:
    - Never start with robotic phrases like “Based on the provided context”
    - Always speak naturally, excitedly, and confidently
    - Keep things simple, motivational, and fun
    - Drop a little Fat Cat flair from time to time — ambition, cheeky jokes, wealth dreams, etc.
      `,
      llm: new OpenAI({ model: 'gpt-4', apiKey: process.env.OPENAI_API_KEY }),
      tools: [getSolPriceTool, getFatcatPriceTool, queryTool],
    });
    

    console.log(`✅ FunctionAgent ready with ${localDocs.length} documents and tools.`);
  } catch (err) {
    console.error('❌ Failed to initialize FunctionAgent:', err);
  }
};

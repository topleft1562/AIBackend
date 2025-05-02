import path from 'path';
import axios from 'axios';
import { Document } from '@llamaindex/core';
import { SimpleDirectoryReader } from '@llamaindex/readers/directory';
import { VectorStoreIndex } from '@llamaindex/core';
import { FunctionTool } from '@llamaindex/core/tools/function';
import { ChatEngine } from '@llamaindex/core/chat_engine';

const FATCAT_MINT = 'AHdVQs56QpEEkRx6m8yiYYEiqM2sKjQxVd6mGH12pump';
const SOL_MINT = 'So11111111111111111111111111111111111111112';

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

  const amount = 1_000_000; // 1 token in base units
  const res = await axios.get(
    `https://quote-api.jup.ag/v6/quote?inputMint=${mint}&outputMint=${SOL_MINT}&amount=${amount}`
  );
  const outAmount = parseFloat(res.data.outAmount) / 1e9;
  const solPrice = await fetchTokenPrice('SOL', SOL_MINT);
  const price = outAmount * solPrice;
  cachedPrices[symbol] = { price, lastUpdated: now };
  return price;
}

const getSolPriceTool = FunctionTool.fromDefaults({
  name: 'get_sol_price',
  description: 'Returns the current price of SOL in USD.',
  fn: async () => {
    const price = await fetchTokenPrice('SOL', SOL_MINT);
    return `1 SOL = $${price.toFixed(4)}`;
  }
});

const getFatcatPriceTool = FunctionTool.fromDefaults({
  name: 'get_fatcat_price',
  description: 'Returns the current price of $FATCAT in USD.',
  fn: async () => {
    const price = await fetchTokenPrice('FATCAT', FATCAT_MINT);
    return `1 $FATCAT = $${price.toFixed(6)}`;
  }
});

let queryEngine2: any;
export const getQueryEngine2 = () => queryEngine2;

export const createQueryEngine2 = async () => {
  try {
    const docsPath = path.join(process.cwd(), 'docs2');
    const localDocs = await new SimpleDirectoryReader().loadData({ directoryPath: docsPath });

    const sol = await fetchTokenPrice('SOL', SOL_MINT);
    const fatcat = await fetchTokenPrice('FATCAT', FATCAT_MINT);

    const priceDoc = new Document({
      text: `\n📈 Real-time Token Prices:\n\n• 1 SOL = $${sol.toFixed(4)}\n• 1 $FATCAT = $${fatcat.toFixed(6)}\n\nPrices auto-refresh every 5 minutes.`,
      metadata: { type: 'price' },
    });

    const allDocs = [...localDocs, priceDoc];
    const index = await VectorStoreIndex.fromDocuments(allDocs);

    queryEngine2 = await ChatEngine.fromDefaults({
      index,
      tools: [getSolPriceTool, getFatcatPriceTool]
    });

    console.log(`✅ Query Engine 2 initialized with ${allDocs.length} documents.`);
  } catch (err) {
    console.error('❌ Failed to initialize Query Engine 2:', err);
  }
};

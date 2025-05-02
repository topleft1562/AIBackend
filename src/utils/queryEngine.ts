import path from 'path';
import axios from 'axios';
import { SimpleDirectoryReader } from '@llamaindex/readers/directory';
import { FunctionTool } from '@llamaindex/core/tools';
import { VectorStoreIndex } from 'llamaindex';

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

let queryEngine2: any;
export const getQueryEngine2 = () => queryEngine2;

export const createQueryEngine2 = async () => {
  try {
    const docsPath = path.join(process.cwd(), 'docs2');
    const localDocs = await new SimpleDirectoryReader().loadData({ directoryPath: docsPath });

    const sol = await fetchTokenPrice('SOL', SOL_MINT);
    const fatcat = await fetchTokenPrice('FATCAT', FATCAT_MINT);


    const allDocs = [...localDocs];
    const index = await VectorStoreIndex.fromDocuments(allDocs);

    queryEngine2 = new FunctionCallingAgent({
      tools: [getSolPriceTool, getFatcatPriceTool],
      llm: undefined, // your OpenAI config or LLM instance here if needed
      retriever: index.asRetriever(),
    });

    console.log(`✅ Query Engine 2 initialized with ${allDocs.length} documents.`);
  } catch (err) {
    console.error('❌ Failed to initialize Query Engine 2:', err);
  }
};

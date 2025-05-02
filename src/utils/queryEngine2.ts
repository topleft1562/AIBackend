import path from 'path';
import { SimpleDirectoryReader } from '@llamaindex/readers/directory';
import { VectorStoreIndex } from '@llamaindex/core';
import { SimpleChatEngine } from '@llamaindex/core/chat_engine';

let queryEngine2: any;
export const getQueryEngine2 = () => queryEngine2;

export const createQueryEngine2 = async () => {
  const reader = new SimpleDirectoryReader();
  const docsPath = path.join(process.cwd(), 'docs');
  const docs = await reader.loadData({ directoryPath: docsPath });
  const index = await VectorStoreIndex.fromDocuments(docs);
  queryEngine2 = new SimpleChatEngine(index.asRetriever());
  console.log('✅ Query Engine 2 initialized');
};

await createQueryEngine2();
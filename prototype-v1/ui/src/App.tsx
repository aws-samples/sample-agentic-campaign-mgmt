// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import ChatAssistant from './pages/ChatAssistant';
import Dashboard from './pages/Dashboard';
import CampaignExplorer from './pages/CampaignExplorer';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

function App() {
  const [selectedTrader, setSelectedTrader] = useState('trader_alpha');

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout selectedTrader={selectedTrader} onTraderChange={setSelectedTrader}>
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatAssistant traderId={selectedTrader} />} />
            <Route path="/dashboard" element={<Dashboard traderId={selectedTrader} />} />
            <Route path="/campaigns" element={<CampaignExplorer traderId={selectedTrader} />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;

// src/App.tsx
import Layout from './components/Layout';
import { Toaster } from './components/ui/sonner';
import BacktestDemo from './components/BacktestDemo';

export default function App() {
  return (
    <Layout>
      <BacktestDemo />
      <Toaster />
    </Layout>
  );
}

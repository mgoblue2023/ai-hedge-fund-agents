// app/frontend/src/App.tsx
import { Layout } from './components/Layout'; // NOTE: capital "L" in Layout
import { Toaster } from './components/ui/sonner';

export default function App() {
  return (
    <Layout>
      <Toaster />
    </Layout>
  );
}


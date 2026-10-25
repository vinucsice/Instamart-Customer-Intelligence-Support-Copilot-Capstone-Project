import { Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import Header from "@/components/cx/Header";
import Overview from "@/pages/Overview";
import DataQuality from "@/pages/DataQuality";
import Segments from "@/pages/Segments";
import Triage from "@/pages/Triage";
import Copilot from "@/pages/Copilot";

// One <Route> per page in src/pages; BrowserRouter already wraps this in main.tsx.
export default function App() {
  return (
    <div className="min-h-svh">
      <Header />
      <main className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6 lg:px-8">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/data-quality" element={<DataQuality />} />
          <Route path="/segments" element={<Segments />} />
          <Route path="/triage" element={<Triage />} />
          <Route path="/copilot" element={<Copilot />} />
          <Route path="*" element={<Overview />} />
        </Routes>
      </main>
      <Toaster />
    </div>
  );
}
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { RunList } from "./components/history/RunList";
import { RunPage } from "./components/layout/RunPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<RunList />} />
        <Route path="/runs/:runId" element={<RunPage />} />
      </Routes>
    </BrowserRouter>
  );
}

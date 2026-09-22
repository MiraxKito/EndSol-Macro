import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { ConfigProvider } from "./contexts/ConfigContext";


document.addEventListener('contextmenu', event => event.preventDefault());

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <ConfigProvider>
      <App />
    </ConfigProvider>
  </StrictMode>,
);

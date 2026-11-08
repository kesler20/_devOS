import * as ReactDOM from "react-dom/client";
import { ReactFlowProvider } from "react-flow-renderer";
import App from "./App";
import "./index.css";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root element not found");
}

const root = ReactDOM.createRoot(rootElement);
root.render(<ReactFlowProvider><App /></ReactFlowProvider>);

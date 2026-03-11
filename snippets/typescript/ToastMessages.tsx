import { toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

export type MessageSeverityType = "success" | "info" | "warning" | "error";

export enum MessageSeverity {
  SUCCESS = "success",
  INFO = "info",
  WARNING = "warning",
  ERROR = "error",
}

export default function toastFactory(
  alertMessage: string,
  severity: MessageSeverity
) {
  switch (severity) {
    case "success":
      return toast.success(alertMessage, { className: "custom-toast-success" });
    case "info":
      return toast.info(alertMessage, { className: "custom-toast-info" });
    case "warning":
      return toast.warning(alertMessage, { className: "custom-toast-warning" });
    case "error":
      return toast.error(alertMessage, { className: "custom-toast-error" });
    default:
      return toast(alertMessage);
  }
}

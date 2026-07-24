import express, { NextFunction, Request, Response } from "express";
import { TextractClient, AnalyzeExpenseCommand } from "@aws-sdk/client-textract";
import { randomUUID } from "crypto";
import multer from "multer";
import cors from "cors";

// ---------------------- //
//                        //
//    App Configuration   //
//                        //
// ---------------------- //

const app = express();
app.use(express.json());
app.use(
  cors({
    origin: ["http://localhost:5173", "https://kesler20.github.io"],
    credentials: true,
  }),
);

const textractClient = new TextractClient({
  region: process.env.AWS_REGION || "us-east-1",
});

// check for required AWS environment variables
const REQUIRED_ENV = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"];
const missingEnv = REQUIRED_ENV.filter((key) => !process.env[key]);

if (missingEnv.length > 0) {
  console.warn(
    `Missing AWS credentials (${missingEnv.join(
      ", ",
    )}). Textract requests will fail until they are set.`,
  );
}

// ================================== //
//                                    //
//   RECEIPT PROCESSING ENDPOINTS     //
//                                    //
// ================================== //

class ReceiptParser {
  static parseCurrency(value: string | undefined | null): number {
    if (!value) return 0;
    const sanitized = value.replace(/[^0-9.-]/g, "");
    const parsed = Number.parseFloat(sanitized);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  static normalizeDate(value: string | undefined | null): string {
    if (!value) {
      return new Date().toISOString().split("T")[0];
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return new Date().toISOString().split("T")[0];
    }
    return parsed.toISOString().split("T")[0];
  }

  static parseExpenseResponse(response: any): any {
    const result: any = { lineItems: [] };
    if (!response?.ExpenseDocuments || response.ExpenseDocuments.length === 0) {
      return result;
    }

    const expenseDoc = response.ExpenseDocuments[0];

    if (expenseDoc.SummaryFields) {
      for (const field of expenseDoc.SummaryFields) {
        const fieldType = field.Type?.Text?.toUpperCase();
        const value = field.ValueDetection?.Text;

        if (!value) continue;

        switch (fieldType) {
          case "VENDOR_NAME":
            result.vendorName = value;
            break;
          case "VENDOR_PHONE":
            result.vendorPhone = value;
            break;
          case "VENDOR_ADDRESS":
            result.vendorAddress = value;
            break;
          case "INVOICE_RECEIPT_DATE":
            result.invoiceDate = value;
            break;
          case "SUBTOTAL":
            result.subtotal = value;
            break;
          case "TAX":
            result.tax = value;
            break;
          case "TOTAL":
            result.total = value;
            break;
          default:
            break;
        }
      }
    }

    if (expenseDoc.LineItemGroups) {
      for (const lineItemGroup of expenseDoc.LineItemGroups) {
        if (!lineItemGroup.LineItems) continue;

        for (const lineItem of lineItemGroup.LineItems) {
          const item: any = { description: "" };

          if (lineItem.LineItemExpenseFields) {
            for (const field of lineItem.LineItemExpenseFields) {
              const fieldType = field.Type?.Text?.toUpperCase();
              const value = field.ValueDetection?.Text;

              if (!value) continue;

              switch (fieldType) {
                case "ITEM":
                  item.description = value;
                  break;
                case "QUANTITY":
                  item.quantity = value;
                  break;
                case "PRICE":
                  item.unitPrice = value;
                  break;
                case "AMOUNT":
                  item.amount = value;
                  break;
                default:
                  break;
              }
            }
          }

          if (item.description) {
            result.lineItems.push(item);
          }
        }
      }
    }

    return result;
  }

  static buildReceiptFromExtracted(extracted: any): any {
    const items = (extracted.lineItems || []).map((item: any) => {
      const quantity = Math.max(1, Number.parseInt(item.quantity ?? "1", 10) || 1);
      const amount = ReceiptParser.parseCurrency(item.amount);
      const unitPrice = ReceiptParser.parseCurrency(item.unitPrice);
      const price = amount > 0 ? amount : unitPrice * quantity;

      return {
        id: randomUUID(),
        name: item.description,
        quantity,
        price,
        assignedTo: [],
      };
    });

    const totalAmount =
      ReceiptParser.parseCurrency(extracted.total) ||
      items.reduce((sum: number, item: any) => sum + item.price, 0);

    return {
      id: randomUUID(),
      merchant: extracted.vendorName ?? "Unknown merchant",
      date: ReceiptParser.normalizeDate(extracted.invoiceDate),
      items,
      totalAmount,
    };
  }
}

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 5 * 1024 * 1024 },
});

app.post("/receipts/analyze", upload.single("receipt"), async (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: "Receipt file is required" });
  }

  if (
    !req.file.mimetype.startsWith("image/") &&
    req.file.mimetype !== "application/pdf"
  ) {
    return res
      .status(400)
      .json({ error: "Only image or PDF uploads are supported" });
  }

  try {
    const command = new AnalyzeExpenseCommand({
      Document: { Bytes: req.file.buffer },
    });
    const data = await textractClient.send(command);

    // Use ReceiptParser class for parsing and building the receipt
    const extracted = ReceiptParser.parseExpenseResponse(data);
    const receipt = ReceiptParser.buildReceiptFromExtracted(extracted);

    return res.json({ receipt });
  } catch (error) {
    console.error("Error processing receipt", error);
    return res.status(500).json({ error: "Failed to process receipt" });
  }
});

// Global error handler - only log message and first stack line
app.use((err: any, req: Request, res: Response, next: NextFunction) => {
  const message = err?.message ?? "Internal Server Error";
  const firstStackLine =
    typeof err?.stack === "string" ? err.stack.split("\n")[0] : undefined;

  console.error(message);
  if (firstStackLine) console.error(firstStackLine);

  res.status(err?.status ?? 500).json({ error: message });
});

// Start the server
const port = 3000;
app.listen(port, () => {
  console.info(`Server is running on port ${port}`);
});

import { FileIO } from "../src/file_io";
import express, { NextFunction, Request, Response } from "express";
import cors from "cors";
import { z } from "zod";

const app = express();
app.use(express.json());
app.use(cors());

// ================================== //
//                                    //
//   CONTRACT FOR THE FILE ENDPOINTS  //
//                                    //
// ================================== //

const FileUploadServiceBodySchema = z.object({
  resourceName: z.string(),
  resourcePath: z.string(),
  resourceContent: z.string(),
});

const FolderParamsSchema = z.object({
  folder: z.string(),
});

const FolderFileParamsSchema = z.object({
  folder: z.string(),
  filename: z.string(),
});

// ---------------------------------------------------------------------------//
//                                                                            //
//      SPECIFIC CRUD FUNCTIONS TO EXPOSE THE FILE-SYSTEM TO THE FRONTEND     //
//                                                                            //
// ---------------------------------------------------------------------------//

// Create endpoint
app.post("/files", async (req: Request, res: Response, next: NextFunction) => {
  try {
    const { resourceName, resourcePath, resourceContent } =
      FileUploadServiceBodySchema.parse(req.body);
    const file = new FileIO(resourcePath);
    await file.createFileAsync(resourceName, resourceContent);
    res.status(201).json({ message: "File created successfully" });
  } catch (error: any) {
    next(error);
  }
});

// Read endpoint
app.get(
  "/files/:folder/:filename",
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { folder, filename } = FolderFileParamsSchema.parse(req.params);
      const file = new FileIO(folder);
      const fileContent = await file.readFileAsync(filename);
      if (fileContent === undefined) {
        res.status(404).json({ message: "File not found" });
        return;
      }
      res.json(JSON.parse(fileContent));
    } catch (error: any) {
      next(error);
    }
  },
);

// Read all files in a folder
app.get(
  "/files/:folder",
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { folder } = FolderParamsSchema.parse(req.params);
      const file = new FileIO(folder);
      const filesInFolder = await file.readFilesAsync();
      const fileContentInFolderPromises = filesInFolder.map((fileName) =>
        file
          .readFileAsync(fileName)
          .then((content) => content && JSON.parse(content)),
      );
      const fileContentInFolder = await Promise.all(fileContentInFolderPromises);
      res.json(fileContentInFolder);
    } catch (error: any) {
      next(error);
    }
  },
);

// Update endpoint
app.patch("/files", async (req: Request, res: Response, next: NextFunction) => {
  try {
    const { resourceName, resourcePath, resourceContent } =
      FileUploadServiceBodySchema.parse(req.body);
    const file = new FileIO(resourcePath);
    await file.updateFileAsync(resourceName, resourceContent);
    res.status(200).json({ message: "File updated successfully" });
  } catch (error: any) {
    next(error);
  }
});

// Delete endpoint
app.delete(
  "/files/:folder/:filename",
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { folder, filename } = FolderFileParamsSchema.parse(req.params);
      const file = new FileIO(folder);
      await file.deleteFileAsync(filename);
      res.status(200).json({ message: "File deleted successfully" });
    } catch (error: any) {
      next(error);
    }
  },
);

// ---------------------- //
//                        //
//     Server Startup     //
//                        //
// ---------------------- //

// Global error handler
app.use((err: any, _req: Request, res: Response, _next: NextFunction) => {
  console.error(err);
  if (err instanceof z.ZodError) {
    res.status(400).json({ error: "Invalid request", details: err.errors });
    return;
  }

  res.status(500).json({ error: err?.message || "Internal Server Error" });
});

// Start the server
const port = 3000;
app.listen(port, () => {
  console.info(`Server is running on port ${port}`);
});

import path from "path";
import fs from "fs";

export class FileIO {
  basePath: string;

  constructor(resourceName: string) {
    this.basePath = path.join("@db", resourceName);
    if (!fs.existsSync(this.basePath)) {
      fs.mkdirSync(this.basePath, { recursive: true });
    }
  }
  private debug(error: any) {
    console.error(error);
  }

  // Create a new file
  createFile(fileName: string, data: string): void {
    const filePath = path.join(this.basePath, fileName);
    fs.writeFileSync(filePath, data);
  }

  // Read the contents of a file
  readFile(fileName: string): string {
    const filePath = path.join(this.basePath, fileName);
    return fs.readFileSync(filePath, "utf-8");
  }

  // Read all the files in the folder
  readFiles(): string[] {
    return fs.readdirSync(this.basePath);
  }

  // Update the contents of a file
  updateFile(fileName: string, data: string): void {
    const filePath = path.join(this.basePath, fileName);
    fs.writeFileSync(filePath, data);
  }

  // Delete a file
  deleteFile(fileName: string): void {
    const filePath = path.join(this.basePath, fileName);
    fs.unlinkSync(filePath);
  }

  // Create a new file
  async createFileAsync(fileName: string, data: string): Promise<void> {
    const filePath = path.join(this.basePath, fileName);
    await fs.writeFile(filePath, data, this.debug);
  }

  // Read the contents of a file
  async readFileAsync(fileName: string): Promise<string | undefined> {
    try {
      const filePath = path.join(this.basePath, fileName);
      const data = await new Promise<string>((resolve, reject) => {
        fs.readFile(filePath, "utf-8", (err, data) => {
          if (err) {
            reject(err);
          } else {
            resolve(data);
          }
        });
      });
      return data;
    } catch (error) {
      this.debug(error);
    }
  }

  // Read all the files in the folder
  async readFilesAsync(): Promise<string[]> {
    try {
      const files = await new Promise<string[]>((resolve, reject) => {
        fs.readdir(this.basePath, (err: NodeJS.ErrnoException | null, files: string[]) => {
          if (err) {
            reject(err);
          } else {
            resolve(files);
          }
        });
      });
      return files;
    } catch (error) {
      this.debug(error);
      throw error;
    }
  }

  // Update the contents of a file
  async updateFileAsync(fileName: string, data: string): Promise<void> {
    const filePath = path.join(this.basePath, fileName);
    await fs.writeFile(filePath, data, this.debug);
  }

  // Delete a file
  async deleteFileAsync(fileName: string): Promise<void> {
    const filePath = path.join(this.basePath, fileName);
    await fs.unlink(filePath, this.debug);
  }
}

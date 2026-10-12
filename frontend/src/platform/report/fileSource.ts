import { createContext } from "react";
import { fileLink } from "../../lib/api";

/** Where the report's PDFs come from: a signed link from the API, or static files of the demo. */
export type FileSource = (checkId: string, name: string) => Promise<string>;

export const staticFileSource = (base: string): FileSource =>
  async (_checkId, name) => `${base}/files/${encodeURIComponent(name)}`;

export const FileSourceContext = createContext<FileSource>(fileLink);

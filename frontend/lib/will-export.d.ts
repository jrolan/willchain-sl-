declare module "@/lib/will-export.mjs" {
  export function buildWillDocumentText(will: {
    title?: string;
    status?: string;
    content?: Record<string, unknown>;
  }): string;

  export function buildWillDocumentHtml(will: {
    title?: string;
    status?: string;
    content?: Record<string, unknown>;
  }): string;
}

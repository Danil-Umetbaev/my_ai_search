export const knowledgeSpace = import.meta.env.VITE_KNOWLEDGE_SPACE || "customer-knowledge";

export function isSourceUrl(url) {
  return typeof url === "string" && (
    /^https?:\/\//i.test(url) ||
    /^\/api\/v1\/knowledge-assets\/[a-zA-Z0-9._-]+(?:#page=\d+)?$/.test(url)
  );
}

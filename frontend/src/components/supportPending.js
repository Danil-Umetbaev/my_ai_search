export function pendingForSession(pending, data) {
  if (pending?.session !== data.id) return null;
  const applied = data.history?.some(entry => entry.role === "assistant" && entry.request_id === pending.id);
  return applied ? null : pending;
}

function requestId() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
  return [hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16), hex.slice(16, 20), hex.slice(20)].join("-");
}

export function outgoingMessage(pending, session, message, choiceId, newId = requestId) {
  if (pending?.session === session) return pending;
  return { id: newId(), session, message, choiceId };
}

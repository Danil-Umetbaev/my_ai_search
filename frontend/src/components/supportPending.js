export function pendingForSession(pending, data) {
  if (pending?.session !== data.id) return null;
  const applied = data.history?.some(entry => entry.role === "assistant" && entry.request_id === pending.id);
  return applied ? null : pending;
}

export function outgoingMessage(pending, session, message, choiceId, newId) {
  if (pending?.session === session) return pending;
  return { id: newId(), session, message, choiceId };
}

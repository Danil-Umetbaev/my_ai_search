const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "/api/v1"
).replace(/\/$/, "")


export class ApiError extends Error {
  constructor({
    message,
    userMessage,
    status = null,
    code = "UNKNOWN_ERROR",
    payload = null,
    cause = null,
  }) {
    super(message)

    this.name = "ApiError"
    this.status = status
    this.code = code
    this.userMessage = userMessage
    this.payload = payload
    this.cause = cause
  }
}


function getUserMessage(status, code, fallback) {
  switch (code) {
    case "CONVERSATION_NOT_FOUND":
      return "Этот диалог больше не существует. Создайте новый диалог."

    case "RAG_PROCESSING_ERROR":
      return "Не удалось обработать вопрос. Попробуйте отправить его ещё раз."

    case "AI_SERVICE_UNAVAILABLE":
      return "AI-сервис временно недоступен. Попробуйте ещё раз чуть позже."

    case "DATABASE_ERROR":
      return "Сервис временно не может получить данные. Попробуйте ещё раз."

    case "INTERNAL_ERROR":
      return "На сервере произошла ошибка. Попробуйте ещё раз."

    default:
      break
  }

  if (status === 404) {
    return "Запрошенные данные не найдены."
  }

  if (status === 422) {
    return "Не удалось отправить запрос. Проверьте введённые данные."
  }

  if (status === 429) {
    return "Слишком много запросов. Подождите немного и попробуйте снова."
  }

  if (status === 503) {
    return "Сервис временно недоступен. Попробуйте ещё раз чуть позже."
  }

  if (status >= 500) {
    return "На сервере произошла ошибка. Попробуйте ещё раз."
  }

  return fallback || "Не удалось выполнить запрос."
}


async function request(path, options = {}) {
  let response

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    })
  } catch (error) {
    throw new ApiError({
      message: "Network request failed",
      userMessage:
        "Не удалось связаться с сервером. Проверьте соединение и попробуйте ещё раз.",
      code: "NETWORK_ERROR",
      cause: error,
    })
  }


  if (!response.ok) {
    let payload = null

    try {
      payload = await response.json()
    } catch {
      // Сервер мог вернуть ответ без JSON.
    }

    const code =
      payload?.code ||
      "HTTP_ERROR"

    const detail = payload?.message || payload?.detail
    const message = typeof detail === "string" ? detail : `HTTP ${response.status}`

    if (response.status === 401 && !path.startsWith("/auth/")) {
      window.dispatchEvent(new Event("auth:expired"))
    }

    throw new ApiError({
      message,
      userMessage: getUserMessage(
        response.status,
        code,
        message
      ),
      status: response.status,
      code,
      payload,
    })
  }


  if (response.status === 204) {
    return null
  }


  try {
    return await response.json()
  } catch (error) {
    throw new ApiError({
      message: "Invalid JSON response",
      userMessage:
        "Сервер вернул некорректный ответ. Попробуйте ещё раз.",
      status: response.status,
      code: "INVALID_RESPONSE",
      cause: error,
    })
  }
}


export function healthCheck() {
  return request("/health")
}

export function getCurrentUser() {
  return request("/auth/me", { cache: "no-store", signal: AbortSignal.timeout(10000) })
}

export function loginUser(email, password) {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  })
}

export function registerUser(email, password, role) {
  return request("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, role }),
  })
}

export function logoutUser() {
  return request("/auth/logout", { method: "DELETE" })
}


export function createConversation() {
  return request("/conversations", {
    method: "POST",
  })
}


export function getMessageHistory(conversationId) {
  return request(
    `/conversations/${conversationId}/messages`
  )
}


export function sendMessage(
  conversationId,
  message
) {
  return request("/chat/messages", {
    method: "POST",
    body: JSON.stringify({
      conversation_id: conversationId,
      message,
    }),
  })
}

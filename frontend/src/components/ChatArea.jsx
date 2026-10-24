import {
  useEffect,
  useRef,
  useState,
} from "react";

import { Icon } from "./Icons.jsx";


function AssistantIcon() {
  return (
    <div
      className="assistant-avatar"
      aria-hidden="true"
    >
      ✦
    </div>
  );
}


function getSourceUrl(source) {
  const url = source?.url?.trim();

  if (!url) {
    return null;
  }

  if (
    url.startsWith("http://") ||
    url.startsWith("https://") ||
    url.startsWith("/")
  ) {
    return url;
  }

  return null;
}


function MessageSourceItem({
  source,
  index,
}) {
  const url = getSourceUrl(source);

  const content = (
    <>
      <span className="message-source__icon">
        ▤
      </span>

      <span className="message-source__title">
        {source.title || "Источник"}
      </span>

      {url && (
        <Icon
          name="external"
          size={13}
          className="message-source__external"
        />
      )}
    </>
  );

  if (!url) {
    return (
      <div
        key={`source-${source.title}-${index}`}
        className="message-source message-source--static"
        title="Ссылка на источник недоступна"
      >
        {content}
      </div>
    );
  }

  return (
    <a
      key={`${url}-${index}`}
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="message-source message-source--clickable"
      title="Открыть источник"
    >
      {content}
    </a>
  );
}


function MessageSources({ sources }) {
  if (!sources?.length) {
    return null;
  }

  return (
    <div className="message-sources">
      <div className="message-sources__label">
        Источники
      </div>

      <div className="message-sources__items">
        {sources.map((source, index) => (
          <MessageSourceItem
            key={`${source.url || source.title}-${index}`}
            source={source}
            index={index}
          />
        ))}
      </div>
    </div>
  );
}


async function copyToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");

  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";

  document.body.appendChild(textarea);

  textarea.select();
  document.execCommand("copy");

  document.body.removeChild(textarea);
}


export default function ChatArea({
  messages,
  sending,
  loading,
  onSend,
  scrollTargetId,
  onScrollTargetHandled,
}) {
  const [value, setValue] = useState("");
  const [copiedMessageId, setCopiedMessageId] = useState(null);

  const messagesRef = useRef(null);
  const copiedTimerRef = useRef(null);


  useEffect(() => {
    if (!messagesRef.current) {
      return;
    }

    messagesRef.current.scrollTo({
      top: messagesRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, sending]);


  useEffect(() => {
    if (!scrollTargetId) {
      return;
    }

    const target = document.getElementById(
      `message-${scrollTargetId}`
    );

    if (target) {
      target.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });

      target.classList.add(
        "message-highlight"
      );

      setTimeout(() => {
        target.classList.remove(
          "message-highlight"
        );
      }, 900);
    }

    onScrollTargetHandled?.();

  }, [
    scrollTargetId,
    onScrollTargetHandled,
  ]);


  useEffect(() => {
    return () => {
      if (copiedTimerRef.current) {
        clearTimeout(copiedTimerRef.current);
      }
    };
  }, []);


  function submit(event) {
    event.preventDefault();

    const text = value.trim();

    if (!text || sending) {
      return;
    }

    onSend(text);
    setValue("");
  }


  function handleKeyDown(event) {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();
      submit(event);
    }
  }


  async function handleCopy(message) {
    if (!message?.content) {
      return;
    }

    try {
      await copyToClipboard(message.content);

      setCopiedMessageId(message.id);

      if (copiedTimerRef.current) {
        clearTimeout(copiedTimerRef.current);
      }

      copiedTimerRef.current = setTimeout(() => {
        setCopiedMessageId(null);
      }, 1400);

    } catch (error) {
      console.error(
        "Не удалось скопировать ответ:",
        error
      );
    }
  }


  function findPreviousUserQuestion(messageIndex) {
    for (
      let index = messageIndex - 1;
      index >= 0;
      index -= 1
    ) {
      if (messages[index]?.role === "user") {
        return messages[index];
      }
    }

    return null;
  }


  function handleRetry(messageIndex) {
    if (sending) {
      return;
    }

    const currentMessage =
      messages[messageIndex];

    const retryText =
      currentMessage?.failedQuestion ||
      findPreviousUserQuestion(messageIndex)?.content;

    if (!retryText) {
      return;
    }

    onSend(retryText);
  }


  return (
    <div className="chat-area">
      <aside className="knowledge-banner" aria-label="База знаний">
        <strong>Спросите о SetRetail10</strong>
        <a href="https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/overview" target="_blank" rel="noopener noreferrer">Открыть базу знаний ↗</a>
      </aside>

      <div
        className="chat-messages"
        ref={messagesRef}
      >
        <div className="chat-thread">

          {loading ? (
            <div className="chat-empty">
              Загружаем диалог…
            </div>
          ) : messages.length === 0 ? (
            <div className="chat-empty">

              <div className="chat-empty__mark">
                ✦
              </div>

              <strong>
                Что хотите узнать?
              </strong>

              <span>
                Например: как создать товарные полки в SetRetail10?
              </span>

            </div>
          ) : (
            messages.map((message, messageIndex) => {
              const user =
                message.role === "user";

              const error =
                message.role === "error" ||
                message.status === "error";

              const copied =
                copiedMessageId === message.id;

              return (
                <div
                  key={message.id}
                  id={`message-${message.id}`}

                  className={[
                    "message-row",

                    user
                      ? "message-row--user"
                      : "message-row--assistant",

                    message.status === "escalated"
                      ? "message-row--escalated"
                      : "",

                    error
                      ? "message-row--error"
                      : "",
                  ].join(" ")}
                >

                  {user ? (
                    <div className="message-bubble message-bubble--user">
                      <div className="message-text">
                        {message.content}
                      </div>
                    </div>
                  ) : (
                    <>
                      <AssistantIcon />

                      <div className="assistant-response">

                        <div className="assistant-response__body">

                          {message.status === "escalated" && (
                            <div className="assistant-response__status">
                              Передано специалистам
                            </div>
                          )}

                          {error && (
                            <div className="assistant-response__status assistant-response__status--error">
                              Не удалось получить ответ
                            </div>
                          )}

                          <div className="message-text">
                            {message.content}
                          </div>

                        </div>

                        {!error && messageIndex === messages.length - 1 && message.choices?.length > 0 && (
                          <div className="reply-choices">
                            {message.choices.map((choice) => (
                              <button key={choice} type="button" disabled={sending} onClick={() => onSend(choice)}>{choice}</button>
                            ))}
                          </div>
                        )}

                        {!error && (
                          <MessageSources
                            sources={message.sources}
                          />
                        )}

                        <div className="assistant-response__actions">
                          {!error && (
                            <button
                              type="button"
                              className={[
                                "message-action",
                                copied
                                  ? "is-success"
                                  : "",
                              ].join(" ")}
                              onClick={() =>
                                handleCopy(message)
                              }
                              title={
                                copied
                                  ? "Скопировано"
                                  : "Копировать ответ"
                              }
                              aria-label={
                                copied
                                  ? "Ответ скопирован"
                                  : "Копировать ответ"
                              }
                            >
                              <Icon
                                name={
                                  copied
                                    ? "check"
                                    : "copy"
                                }
                                size={15}
                              />

                              {copied && (
                                <span>
                                  Скопировано
                                </span>
                              )}
                            </button>
                          )}

                          <button
                            type="button"
                            className={[
                              "message-action",
                              error
                                ? "message-action--retry-error"
                                : "",
                            ].join(" ")}
                            onClick={() =>
                              handleRetry(messageIndex)
                            }
                            disabled={sending}
                            title="Повторить запрос"
                            aria-label="Повторить запрос"
                          >
                            <Icon
                              name="refresh"
                              size={15}
                            />

                            {error && (
                              <span>
                                Повторить
                              </span>
                            )}
                          </button>
                        </div>

                      </div>
                    </>
                  )}

                </div>
              );
            })
          )}


          {sending && (
            <div className="message-row message-row--assistant">

              <AssistantIcon />

              <div className="assistant-response">

                <div className="assistant-response__body">

                  <div className="typing-dots">
                    <span />
                    <span />
                    <span />
                  </div>

                </div>

              </div>

            </div>
          )}

        </div>
      </div>


      <div className="composer-shell">

        <form
          className="composer"
          onSubmit={submit}
        >

          <textarea
            rows={1}
            value={value}

            onChange={(event) =>
              setValue(event.target.value)
            }

            onKeyDown={handleKeyDown}

            placeholder="Спросите что-нибудь…"

            className="composer-input"
          />


          <button
            type="submit"

            className="composer-send"

            disabled={
              sending ||
              !value.trim()
            }
          >
            ➤
          </button>

        </form>

      </div>

    </div>
  );
}

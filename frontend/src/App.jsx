import {
  useEffect,
  useMemo,
  useState,
} from "react";

import Sidebar from "./components/Sidebar";
import ChatArea from "./components/ChatArea";
import DetailsPanel from "./components/DetailsPanel";

import {
  createConversation as createConversationRequest,
  getMessageHistory,
  sendMessage as sendMessageRequest,
} from "./api/client";

import "./styles.css";

const CONVERSATIONS_STORAGE_KEY =
  "ai-search-conversations-v4";

const ACTIVE_CONVERSATION_STORAGE_KEY =
  "ai-search-active-conversation-v4";

const META_STORAGE_KEY =
  "ai-search-message-meta-v4";


function loadJson(key, fallback) {
  try {
    const raw =
      localStorage.getItem(key);

    return raw
      ? JSON.parse(raw)
      : fallback;
  } catch {
    return fallback;
  }
}


function trimText(text, maxLength) {
  if (!text) {
    return "";
  }

  return text.length <= maxLength
    ? text
    : `${text.slice(0, maxLength)}…`;
}


function buildConversationTitle(text) {
  return (
    trimText(text, 34) ||
    "Новый диалог"
  );
}


function buildConversationPreview(text) {
  return trimText(text, 64);
}


function mergeMessagesWithMeta(
  messages,
  meta
) {
  return messages.map(
    (message) => {
      const messageMeta =
        meta?.[message.id];

      return {
        ...message,

        status:
          messageMeta?.status ||
          null,

        sources:
          messageMeta?.sources ||
          [],

        confidence:
          messageMeta?.confidence ??
          null,
      };
    }
  );
}


export default function App() {
  const [
    conversations,
    setConversations,
  ] = useState(() =>
    loadJson(
      CONVERSATIONS_STORAGE_KEY,
      []
    )
  );

  const [
    messageMetaStore,
    setMessageMetaStore,
  ] = useState(() =>
    loadJson(
      META_STORAGE_KEY,
      {}
    )
  );

  const [
    activeConversationId,
    setActiveConversationId,
  ] = useState(() =>
    loadJson(
      ACTIVE_CONVERSATION_STORAGE_KEY,
      null
    )
  );

  const [
    messages,
    setMessages,
  ] = useState([]);

  const [
    sending,
    setSending,
  ] = useState(false);

  const [
    loadingMessages,
    setLoadingMessages,
  ] = useState(false);


  // Левая панель
  const [
    sidebarOpen,
    setSidebarOpen,
  ] = useState(true);


  // Правая панель
  const [
    detailsOpen,
    setDetailsOpen,
  ] = useState(true);

  const [
    detailsPinned,
    setDetailsPinned,
  ] = useState(true);


  const [
    aboutOpen,
    setAboutOpen,
  ] = useState(false);

  const [
    scrollTargetId,
    setScrollTargetId,
  ] = useState(null);


  useEffect(() => {
    localStorage.setItem(
      CONVERSATIONS_STORAGE_KEY,
      JSON.stringify(
        conversations
      )
    );
  }, [conversations]);


  useEffect(() => {
    localStorage.setItem(
      META_STORAGE_KEY,
      JSON.stringify(
        messageMetaStore
      )
    );
  }, [messageMetaStore]);


  useEffect(() => {
    localStorage.setItem(
      ACTIVE_CONVERSATION_STORAGE_KEY,
      JSON.stringify(
        activeConversationId
      )
    );
  }, [activeConversationId]);


  useEffect(() => {
    if (
      !activeConversationId &&
      conversations.length > 0
    ) {
      setActiveConversationId(
        conversations[0].id
      );
    }
  }, [
    activeConversationId,
    conversations,
  ]);


  useEffect(() => {
    if (!activeConversationId) {
      setMessages([]);
      return;
    }

    loadConversationMessages(
      activeConversationId
    );
  }, [activeConversationId]);


  const activeConversation =
    useMemo(() => {
      return (
        conversations.find(
          (conversation) =>
            conversation.id ===
            activeConversationId
        ) || null
      );
    }, [
      conversations,
      activeConversationId,
    ]);


  async function createConversation() {
    try {
      const data =
        await createConversationRequest();

      const conversation = {
        id: data.id,

        created_at:
          data.created_at,

        updated_at:
          data.created_at,

        title:
          "Новый диалог",

        preview:
          "Задайте первый вопрос",
      };

      setConversations(
        (current) => [
          conversation,
          ...current,
        ]
      );

      setActiveConversationId(
        data.id
      );

      setMessages([]);

      return data.id;

    } catch (error) {
      console.error(
        "Не удалось создать conversation:",
        error
      );

      return null;
    }
  }


  async function loadConversationMessages(
    conversationId
  ) {
    setLoadingMessages(true);

    try {
      const data =
        await getMessageHistory(
          conversationId
        );

      const conversationMeta =
        messageMetaStore[
          conversationId
        ] || {};

      setMessages(
        mergeMessagesWithMeta(
          data,
          conversationMeta
        )
      );

    } catch (error) {
      console.error(
        "Не удалось загрузить сообщения:",
        error
      );

      setMessages([]);

    } finally {
      setLoadingMessages(false);
    }
  }


  function saveMessageMeta(
    conversationId,
    messageId,
    meta
  ) {
    setMessageMetaStore(
      (current) => ({
        ...current,

        [conversationId]: {
          ...(
            current[
              conversationId
            ] || {}
          ),

          [messageId]: meta,
        },
      })
    );
  }


  function updateConversation(
    conversationId,
    userText,
    assistantText = ""
  ) {
    setConversations(
      (current) => {
        const updated =
          current.map(
            (conversation) => {
              if (
                conversation.id !==
                conversationId
              ) {
                return conversation;
              }

              const isNew =
                conversation.title ===
                "Новый диалог";

              return {
                ...conversation,

                title: isNew
                  ? buildConversationTitle(
                      userText
                    )
                  : conversation.title,

                preview:
                  buildConversationPreview(
                    assistantText ||
                    userText
                  ),

                updated_at:
                  new Date()
                    .toISOString(),
              };
            }
          );

        return updated.sort(
          (a, b) =>
            new Date(
              b.updated_at
            ).getTime() -
            new Date(
              a.updated_at
            ).getTime()
        );
      }
    );
  }


  async function handleSendMessage(
    text
  ) {
    const question =
      text.trim();

    if (!question || sending) {
      return;
    }

    let conversationId =
      activeConversationId;

    if (!conversationId) {
      conversationId =
        await createConversation();

      if (!conversationId) {
        return;
      }
    }


    const temporaryUserMessage = {
      id:
        `temp-user-${Date.now()}`,

      conversation_id:
        conversationId,

      role: "user",

      content: question,

      created_at:
        new Date()
          .toISOString(),
    };


    setMessages(
      (current) => [
        ...current,
        temporaryUserMessage,
      ]
    );


    updateConversation(
      conversationId,
      question
    );


    setSending(true);


    try {
      const data =
        await sendMessageRequest(
          conversationId,
          question
        );


      const assistantText =
        data.answer ||
        data.message ||
        "Ответ не получен.";


      const assistantMessage = {
        id:
          data.message_id,

        conversation_id:
          conversationId,

        role:
          "assistant",

        content:
          assistantText,

        created_at:
          new Date()
            .toISOString(),

        status:
          data.status || null,

        sources:
          data.sources || [],

        confidence:
          data.confidence ?? null,
      };


      setMessages(
        (current) => [
          ...current,
          assistantMessage,
        ]
      );


      saveMessageMeta(
        conversationId,
        data.message_id,
        {
          status:
            data.status || null,

          sources:
            data.sources || [],

          confidence:
            data.confidence ?? null,
        }
      );


      updateConversation(
        conversationId,
        question,
        assistantText
      );


      if (
        data.status ===
        "escalated"
      ) {
        setDetailsOpen(true);
      }

    } catch (error) {
      console.error(
        "Ошибка отправки сообщения:",
        error
      );


      setMessages(
        (current) => [
          ...current,

          {
            id:
              `error-${Date.now()}`,

            conversation_id:
              conversationId,

            role:
              "error",

            content:
              error.userMessage ||
              "Не удалось получить ответ. Попробуйте ещё раз.",

            created_at:
              new Date()
                .toISOString(),

            status:
              "error",

            sources: [],

            failedQuestion:
              question,

            errorCode:
              error.code ||
              "UNKNOWN_ERROR",
          },
        ]
      );

    } finally {
      setSending(false);
    }
  }


  return (
    <div className="app-shell">

      <Sidebar
        open={
          sidebarOpen
        }

        conversations={
          conversations
        }

        activeConversationId={
          activeConversationId
        }

        onToggle={() =>
          setSidebarOpen(
            (current) => !current
          )
        }

        onSelectConversation={(
          id
        ) => {
          setActiveConversationId(
            id
          );

          setScrollTargetId(
            null
          );
        }}

        onNewConversation={
          createConversation
        }

        onOpenAbout={() =>
          setAboutOpen(true)
        }
      />


      <main
        className={[
          "workspace",

          detailsOpen &&
          detailsPinned
            ? "workspace--details-pinned"
            : "",
        ].join(" ")}
      >

        <section className="chat-column">

          {/*
            Заголовок полностью убран.
            Никаких "Что находится..."
            и никаких подписей под ним.
          */}

          <ChatArea
            messages={messages}

            sending={sending}

            loading={
              loadingMessages
            }

            onSend={
              handleSendMessage
            }

            scrollTargetId={
              scrollTargetId
            }

            onScrollTargetHandled={() =>
              setScrollTargetId(
                null
              )
            }
          />

        </section>


        <button
          type="button"

          className={[
            "details-handle",

            detailsOpen
              ? "is-open"
              : "",
          ].join(" ")}

          onClick={() =>
            setDetailsOpen(
              (current) =>
                !current
            )
          }

          title={
            detailsOpen
              ? "Скрыть панель"
              : "Показать панель"
          }
        >
          {detailsOpen
            ? "›"
            : "‹"}
        </button>


        <DetailsPanel
          open={
            detailsOpen
          }

          pinned={
            detailsPinned
          }

          onTogglePin={() =>
            setDetailsPinned(
              (current) =>
                !current
            )
          }

          messages={
            messages
          }

          onSelectHistoryMessage={(
            messageId
          ) =>
            setScrollTargetId(
              messageId
            )
          }
        />

      </main>


      {aboutOpen && (
        <div
          className="modal-backdrop"

          onClick={() =>
            setAboutOpen(false)
          }
        >
          <div
            className="about-modal"

            onClick={(event) =>
              event.stopPropagation()
            }
          >

            <div className="about-modal__top">

              <img
                src="/logo.png"
                alt="Умный поиск"
              />

              <div>
                <h2>
                  Умный поиск
                </h2>

                <p>
                  Ответы по знаниям вашей компании
                </p>
              </div>


              <button
                type="button"

                onClick={() =>
                  setAboutOpen(false)
                }
              >
                ×
              </button>

            </div>


            <div className="about-modal__body">

              <div className="about-card">
                <strong>
                  Поиск в знаниях
                </strong>

                <p>
                  Система ищет информацию
                  в корпоративной базе документов
                  и формирует ответ на обычный вопрос.
                </p>
              </div>


              <div className="about-card">
                <strong>
                  Проверяемый ответ
                </strong>

                <p>
                  Вместе с ответом отображаются
                  документы, на которых он основан.
                </p>
              </div>


              <div className="about-card">
                <strong>
                  Эскалация
                </strong>

                <p>
                  Если надёжного ответа нет,
                  вопрос автоматически передаётся
                  специалистам.
                </p>
              </div>

            </div>

          </div>
        </div>
      )}

    </div>
  );
}
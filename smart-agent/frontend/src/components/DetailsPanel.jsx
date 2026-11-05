import {
  useMemo,
  useState,
} from "react";

import { Icon } from "./Icons.jsx";


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


function SourceRow({
  source,
  index,
}) {
  const url = getSourceUrl(source);

  const content = (
    <>
      <span className="source-row__icon">
        ▤
      </span>

      <span className="source-row__text">
        {source.title || "Источник"}
      </span>

      {url && (
        <Icon
          name="external"
          size={14}
          className="source-row__external"
        />
      )}
    </>
  );

  if (!url) {
    return (
      <div
        className="source-row source-row--static"
        title="Ссылка на источник недоступна"
      >
        {content}
      </div>
    );
  }

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="source-row source-row--clickable"
      title="Открыть источник"
    >
      {content}
    </a>
  );
}


function PinIcon({
  pinned,
}) {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M9 3h6l-1 6 4 4v2h-5v6l-2-2v-4H6v-2l4-4-1-6Z"

        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"

        fill={
          pinned
            ? "currentColor"
            : "none"
        }
      />
    </svg>
  );
}


function Chevron({
  open,
}) {
  return (
    <span
      className={[
        "details-chevron",

        open
          ? "is-open"
          : "",
      ].join(" ")}
    >
      ›
    </span>
  );
}


function collectSources(
  messages
) {
  const result =
    new Map();

  messages.forEach(
    (message) => {

      if (
        message.role !==
        "assistant"
      ) {
        return;
      }

      (
        message.sources || []
      ).forEach(
        (source) => {

          const key =
            source.url ||
            source.title;

          if (!result.has(key)) {
            result.set(
              key,
              source
            );
          }
        }
      );

    }
  );

  return [
    ...result.values(),
  ];
}


function collectQuestions(
  messages
) {
  return messages.filter(
    (message) =>
      message.role === "user"
  );
}


function collectEscalations(
  messages
) {
  const result = [];

  messages.forEach(
    (message, index) => {

      if (
        message.role !==
          "assistant" ||
        message.status !==
          "escalated"
      ) {
        return;
      }

      let question = null;

      for (
        let i = index - 1;
        i >= 0;
        i -= 1
      ) {
        if (
          messages[i].role ===
          "user"
        ) {
          question =
            messages[i];

          break;
        }
      }

      result.push({
        id: message.id,

        question:
          question?.content ||
          "Вопрос пользователя",

        questionId:
          question?.id ||
          null,
      });

    }
  );

  return result;
}


function Section({
  title,
  count,
  open,
  onToggle,
  children,
}) {
  return (
    <section className="details-section">

      <button
        type="button"
        className="details-section__trigger"
        onClick={onToggle}
      >

        <div>
          <strong>
            {title}
          </strong>

          <span>
            {count}
          </span>
        </div>


        <Chevron
          open={open}
        />

      </button>


      {open && (
        <div className="details-section__content">
          {children}
        </div>
      )}

    </section>
  );
}


export default function DetailsPanel({
  mobile = false,
  onClose,
  open,
  pinned,
  onTogglePin,
  messages,
  onSelectHistoryMessage,
}) {
  const [sections, setSections] =
    useState({
      sources: true,
      history: false,
      escalations: false,
    });


  const sources =
    useMemo(
      () =>
        collectSources(messages),
      [messages]
    );


  const questions =
    useMemo(
      () =>
        collectQuestions(messages),
      [messages]
    );


  const escalations =
    useMemo(
      () =>
        collectEscalations(messages),
      [messages]
    );


  function toggle(name) {
    setSections(
      (current) => ({
        ...current,

        [name]:
          !current[name],
      })
    );
  }


  return (
    <aside
      id="details-panel"
      role={mobile && open ? "dialog" : undefined}
      aria-modal={mobile && open ? true : undefined}
      aria-label="Источники и детали беседы"
      inert={!open ? true : undefined}
      className={[
        "details-panel",

        open
          ? "is-open"
          : "",

        pinned
          ? "is-pinned"
          : "",
      ].join(" ")}
    >

      <div className="details-toolbar">
        {mobile && <>
          <strong>Детали беседы</strong>
          <button type="button" className="mobile-panel-close" onClick={onClose} aria-label="Закрыть детали">×</button>
        </>}

        <button
          type="button"

          className={[
            "details-pin",

            pinned
              ? "is-active"
              : "",
          ].join(" ")}

          onClick={
            onTogglePin
          }

          title={
            pinned
              ? "Открепить панель"
              : "Закрепить панель"
          }
        >
          <PinIcon
            pinned={pinned}
          />
        </button>

      </div>


      <div className="details-content">


        <Section
          title="Источники"
          count={sources.length}

          open={
            sections.sources
          }

          onToggle={() =>
            toggle("sources")
          }
        >

          {sources.length === 0 ? (
            <div className="details-empty">
              Источники появятся после ответа.
            </div>
          ) : (
            <div className="source-list">

              {sources.map(
                (source, index) => (
                  <SourceRow
                    key={`${source.url || source.title}-${index}`}
                    source={source}
                    index={index}
                  />
                )
              )}

            </div>
          )}

        </Section>


        <Section
          title="История"
          count={questions.length}

          open={
            sections.history
          }

          onToggle={() =>
            toggle("history")
          }
        >

          {questions.length === 0 ? (
            <div className="details-empty">
              Вопросов пока нет.
            </div>
          ) : (
            <div className="question-list">

              {questions.map(
                (question) => (
                  <button
                    key={
                      question.id
                    }

                    type="button"

                    className="question-row"

                    onClick={() =>
                      onSelectHistoryMessage(
                        question.id
                      )
                    }
                  >
                    {question.content}
                  </button>
                )
              )}

            </div>
          )}

        </Section>


        <Section
          title="Эскалации"
          count={escalations.length}

          open={
            sections.escalations
          }

          onToggle={() =>
            toggle(
              "escalations"
            )
          }
        >

          {escalations.length === 0 ? (
            <div className="details-empty">
              Эскалаций нет.
            </div>
          ) : (
            <div className="escalation-list">

              {escalations.map(
                (item) => (
                  <button
                    key={item.id}

                    type="button"

                    className="escalation-row"

                    onClick={() => {
                      if (
                        item.questionId
                      ) {
                        onSelectHistoryMessage(
                          item.questionId
                        );
                      }
                    }}
                  >

                    <span>
                      Передано специалистам
                    </span>

                    <strong>
                      {item.question}
                    </strong>

                  </button>
                )
              )}

            </div>
          )}

        </Section>


      </div>

    </aside>
  );
}
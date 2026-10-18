function formatRelativeTime(
  dateString
) {
  if (!dateString) {
    return "";
  }

  const diff =
    Date.now() -
    new Date(
      dateString
    ).getTime();

  const minutes =
    Math.floor(
      diff / 60000
    );

  if (minutes < 1) {
    return "сейчас";
  }

  if (minutes < 60) {
    return `${minutes} мин`;
  }

  const hours =
    Math.floor(
      minutes / 60
    );

  if (hours < 24) {
    return `${hours} ч`;
  }

  return `${Math.floor(
    hours / 24
  )} д`;
}


export default function Sidebar({
  open,

  conversations,

  activeConversationId,

  onToggle,

  onSelectConversation,

  onNewConversation,

  onOpenAbout,
}) {
  return (
    <aside
      className={[
        "sidebar",

        open
          ? "is-open"
          : "is-collapsed",
      ].join(" ")}
    >

      <button
        type="button"

        className="sidebar-toggle"

        onClick={
          onToggle
        }

        title={
          open
            ? "Свернуть панель"
            : "Развернуть панель"
        }
      >
        {open
          ? "‹"
          : "›"}
      </button>


      <button
        type="button"

        className="sidebar-brand"

        onClick={
          onOpenAbout
        }

        title="О проекте"
      >

        <img
          src="/logo.png"
          alt="Умный поиск"
        />


        <div className="sidebar-brand__text">

          <strong>
            Умный поиск
          </strong>

          <span>
            AI Search
          </span>

        </div>

      </button>


      <div className="sidebar-heading">

        <h2>
          Диалоги
        </h2>


        <button
          type="button"

          className="new-chat-button"

          onClick={
            onNewConversation
          }

          title="Новый диалог"
        >
          +
        </button>

      </div>


      <div className="conversation-list">

        {conversations.map(
          (conversation) => {

            const active =
              conversation.id ===
              activeConversationId;

            return (
              <button
                key={
                  conversation.id
                }

                type="button"

                className={[
                  "conversation-item",

                  active
                    ? "is-active"
                    : "",
                ].join(" ")}

                onClick={() =>
                  onSelectConversation(
                    conversation.id
                  )
                }
              >

                <span className="conversation-item__marker" />


                <div className="conversation-item__body">

                  <div className="conversation-item__top">

                    <strong>
                      {conversation.title}
                    </strong>

                    <span>
                      {formatRelativeTime(
                        conversation.updated_at
                      )}
                    </span>

                  </div>


                  <p>
                    {conversation.preview ||
                      "Новый диалог"}
                  </p>

                </div>

              </button>
            );
          }
        )}

      </div>

    </aside>
  );
}
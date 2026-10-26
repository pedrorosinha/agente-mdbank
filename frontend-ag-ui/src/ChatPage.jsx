import { useAppState } from "./StateContext";
import AppLayout from "./Layout";
import ChatBox from "./components/ChatBox";
import PromptSuggestions from "./components/PromptSuggestions";

export default function ChatPage() {
  const {
    state,
    messages,
    setMessages,
    loading,
    setLoading,
    updateState,
  } = useAppState();

  async function sendMessage(message) {
    if (!message?.trim() || loading) return;

    const userMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: message,
    };

    const assistantId = crypto.randomUUID();

    setMessages((prev) => [
      ...prev,
      userMessage,
      {
        id: assistantId,
        role: "assistant",
        content: "",
      },
    ]);

    setLoading(true);

    const updateAssistantMessage = (content) => {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantId
            ? { ...msg, content }
            : msg
        )
      );
    };

    const payload = {
      thread_id: "1",
      run_id: crypto.randomUUID(),
      messages: [
        ...messages.map(({ id, role, content }) => ({
          id,
          role,
          content,
        })),
        userMessage,
      ],
      state,
      tools: [],
      context: [],
      forwardedProps: {},
    };

    let assistantMessage = "";
    let receivedContent = false;

    try {
      const response = await fetch("http://localhost:8080/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(
          `Erro HTTP ${response.status}: ${response.statusText}`
        );
      }

      if (!response.body) {
        throw new Error("O servidor não retornou um stream.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");

      let buffer = "";
      let finished = false;

      function processEvent(event) {
        console.log("Evento AG-UI:", event);

        switch (event.type) {
          case "RUN_STARTED":
            console.log("Execução iniciada.");
            break;

          case "TEXT_MESSAGE_START":
            console.log("Mensagem iniciada:", event.messageId);
            break;

          case "TEXT_MESSAGE_CONTENT":
            receivedContent = true;
            assistantMessage += event.delta || "";
            updateAssistantMessage(assistantMessage);
            break;

          case "STATE_SNAPSHOT":
            console.log("Novo state:", event.snapshot);

            if (event.snapshot) {
              updateState(event.snapshot);
            }
            break;

          // Compatibilidade com eventos personalizados antigos
          case "STATE_UPDATE":
            if (event.state) {
              updateState(event.state);
            }
            break;

          case "TEXT_MESSAGE_END":
            console.log("Mensagem finalizada.");
            break;

          case "RUN_FINISHED":
            console.log("Execução concluída.");
            finished = true;
            break;

          case "RUN_ERROR":
            console.error("Erro AG-UI:", event);

            throw new Error(
              event.message || "Erro durante a execução do agente."
            );

          default:
            console.debug("Evento não tratado:", event.type);
        }
      }

      function processSSEBlock(block) {
        const data = block
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart())
          .join("\n");

        if (!data || data === "[DONE]") return;

        const event = JSON.parse(data);
        processEvent(event);
      }

      while (!finished) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder
          .decode(value, { stream: true })
          .replace(/\r\n/g, "\n");

        const blocks = buffer.split("\n\n");

        // Preserva o último bloco incompleto
        buffer = blocks.pop() || "";

        for (const block of blocks) {
          if (block.trim()) {
            processSSEBlock(block);
          }
        }
      }

      buffer += decoder.decode();

      // Processa eventual último evento sem linha em branco
      if (!finished && buffer.trim()) {
        processSSEBlock(buffer);
      }

      if (!receivedContent) {
        updateAssistantMessage(
          "O agente concluiu a execução sem retornar uma mensagem."
        );
      }
    } catch (error) {
      console.error("Erro no streaming AG-UI:", error);

      updateAssistantMessage(
        assistantMessage
          ? `${assistantMessage}\n\nErro: ${error.message}`
          : `Não foi possível processar sua solicitação.\n\n${error.message}`
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppLayout>
      {messages.length === 0 ? (
        <PromptSuggestions onSelect={sendMessage} />
      ) : (
        <ChatBox
          messages={messages}
          setMessages={setMessages}
          onSend={sendMessage}
          loading={loading}
        />
      )}
    </AppLayout>
  );
}

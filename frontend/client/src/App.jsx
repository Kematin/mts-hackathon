import { useState } from "react";
import ChatWindow from "./app/components/ChatWindow";
import InputBox from "./app/components/InputBox";
import Header from "./app/components/Header";
import ThreadWindow from "./app/components/ThreadWindow";
import "./index.css";

function App() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = async (message) => {
    setMessages((prev) => [...prev, { role: "user", text: message }]);
    setIsLoading(true);

    try {
      const res = await fetch("http://localhost:8000/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: message }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        const errorMessage = errorData.details
          ? `${errorData.error}: ${errorData.details}${errorData.hint ? `\n\n💡 ${errorData.hint}` : ""}`
          : errorData.error || "Failed to get response";
        throw new Error(errorMessage);
      }

      const data = await res.json();
      setMessages((prev) => [...prev, { role: "bot", text: data.response }]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          text: `❌ Error: ${error.message}`,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-gray-900 via-gray-900 to-gray-950 text-white overflow-hidden">
      <Header />
      <div className="flex flex-row flex-1 overflow-y-auto">
        {/* <ThreadWindow /> */}
        <ChatWindow
          messages={messages}
          isLoading={isLoading}
          onSuggestionClick={sendMessage}
        />
      </div>
      <InputBox onSend={sendMessage} isLoading={isLoading} />
    </div>
  );
}

export default App;

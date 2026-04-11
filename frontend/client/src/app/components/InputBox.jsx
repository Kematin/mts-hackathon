import { useState, useRef, useEffect } from "react";
import { Send, Loader2 } from "lucide-react";
import { motion } from "framer-motion";

export default function InputBox({ onSend, isLoading }) {
  const [input, setInput] = useState("");
  const textareaRef = useRef(null);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    const message = input.trim();
    setInput("");
    await onSend(message);
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 128)}px`;
    }
  }, [input]);

  return (
    <div className="border-t border-gray-700/50 bg-gray-900/50 backdrop-blur-sm">
      <div className="max-w-4xl mx-auto px-4 py-4">
        <div className="flex gap-3 items-end">
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              className="w-full bg-gray-800/50 border border-gray-700/50 rounded-2xl px-4 py-3 pr-12 text-gray-100 placeholder-gray-500 
                       focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50
                       resize-none max-h-32 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-transparent
                       transition-all duration-200"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="Type your message... (Press Enter to send, Shift+Enter for new line)"
              disabled={isLoading}
              rows={1}
              style={{
                scrollbarWidth: 'thin',
                scrollbarColor: '#4b5563 transparent'
              }}
            />
            <div className="absolute right-3 bottom-3 text-xs text-gray-500">
              {input.length > 0 && `${input.length}`}
            </div>
          </div>
          <div className="h-[54px]">
            <motion.button
              whileHover={{ scale: isLoading || !input.trim() ? 1 : 1.05 }}
              whileTap={{ scale: isLoading || !input.trim() ? 1 : 0.95 }}
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              className="p-3 bg-gradient-to-br from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 
                      disabled:from-gray-700 disabled:to-gray-700 disabled:cursor-not-allowed 
                      rounded-2xl text-white shadow-lg transition-all duration-200
                      flex items-center justify-center min-w-[48px] min-h-[48px]"
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </motion.button>
          </div>
          
        </div>
        <p className="text-xs text-gray-500 mt-2 text-center">
          LocalScript • Your data stays private
        </p>
      </div>
    </div>
  );
}


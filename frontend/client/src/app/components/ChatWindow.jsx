import { motion, AnimatePresence } from "framer-motion";
import { useRef, useEffect, useState } from "react";
import { User, Bot, Sparkles, ClipboardCopy, RotateCcw } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

export default function ChatWindow({ messages, isLoading, onSuggestionClick }) {
  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);

  const [copiedBlockIndex, setCopiedBlockIndex] = useState(null);

  // Функция копирования для конкретного блока кода
  const handleCopy = (codeText, blockId) => {
    navigator.clipboard.writeText(codeText)
      .then(() => {
        setCopiedBlockIndex(blockId);
        setTimeout(() => setCopiedBlockIndex(null), 2000);
      })
      .catch(err => console.error('Ошибка копирования:', err));
  };

  const handleAddMessage = (newMessage) => {
    
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  return (
    <div 
      ref={chatContainerRef}
      className="flex-1 overflow-y-auto scroll-smooth"
      style={{
        scrollbarWidth: 'thin',
        scrollbarColor: '#4b5563 #1f2937'
      }}
    >
      <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        {messages.length === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col items-center justify-center h-full min-h-[60vh] text-center"
          >
            <div className="mb-6 p-4 bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-2xl">
              <Sparkles className="w-12 h-12 text-blue-400" />
            </div>
            <h2 className="text-2xl font-semibold text-gray-200 mb-2">
              Welcome to LocalScript
            </h2>
            <p className="text-gray-400 max-w-md">
              Start a conversation with your local AI assistant. All processing happens on your device for complete privacy.
            </p>
            <div className="mt-8 flex flex-wrap gap-2 justify-center">
              {["Explain quantum computing", "Write a poem", "Help me code", "Tell me a joke"].map((suggestion, i) => (
                <motion.button
                  key={i}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="px-4 py-2 bg-gray-800/50 hover:bg-gray-700/50 rounded-full text-sm text-gray-300 border border-gray-700/50 transition-colors backdrop-blur-sm"
                  onClick={() => onSuggestionClick && onSuggestionClick(suggestion)}
                >
                  {suggestion}
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}

        <AnimatePresence>
          {messages.map((msg, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              className={`flex gap-3 ${
                msg.role === "user" ? "flex-row-reverse" : "flex-row"
              }`}
            >
              {/* Avatar */}
              <div
                className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                  msg.role === "user"
                    ? "bg-gradient-to-br from-blue-500 to-blue-600"
                    : "bg-gradient-to-br from-purple-500 to-pink-500"
                } shadow-lg`}
              >
                {msg.role === "user" ? (
                  <User className="w-4 h-4 text-white" />
                ) : (
                  <Bot className="w-4 h-4 text-white" />
                )}
              </div>

              {/* Message Bubble */}
              <div className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"} max-w-[75%]`}>
                <div
                  className={`px-4 py-3 rounded-2xl shadow-lg markdown-content ${
                    msg.role === "user"
                      ? "bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-tr-sm"
                      : "bg-gray-800 text-gray-100 border border-gray-700 rounded-tl-sm"
                  }`}
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      // Customize heading styles
                      h1: ({node, ...props}) => <h1 className="text-lg font-bold mt-3 mb-2 first:mt-0" {...props} />,
                      h2: ({node, ...props}) => <h2 className="text-base font-bold mt-3 mb-2 first:mt-0" {...props} />,
                      h3: ({node, ...props}) => <h3 className="text-sm font-semibold mt-2 mb-1 first:mt-0" {...props} />,
                      // Customize paragraph
                      p: ({node, ...props}) => <p className="mb-2 last:mb-0 text-sm leading-relaxed" {...props} />,
                      // Customize lists
                      ul: ({node, ...props}) => <ul className="list-disc list-inside mb-2 space-y-1 ml-2" {...props} />,
                      ol: ({node, ...props}) => <ol className="list-decimal list-inside mb-2 space-y-1 ml-2" {...props} />,
                      li: ({node, ...props}) => <li className="text-sm leading-relaxed" {...props} />,
                      // Customize code blocks
                      code({ node, inline, className, children, ...props }) {
                        const match = /language-(\w+)/.exec(className || '');
                        const language = match ? match[1] : 'text';

                        const codeText = String(children).replace(/\n$/, '');

                        const blockId = `${language}-${codeText.substring(0, 50).replace(/\s+/g, '')}`;
                      
                        return !inline && match ? (
                              // Блок кода: используем SyntaxHighlighter для подсветки
                              <div className="flex flex-col">
                                <div className="flex flex-row justify-between align-center background-gray-700 text-gray-300 text-[14px] px-2 py-1 rounded-tl-sm rounded-tr-sm border border-gray-700">
                                  <div>{language}</div>
                                  <button onClick={() => handleCopy(codeText, blockId)} className="flex flex-row items-center gap-1 text-gray-500 hover:text-white cursor-pointer">
                                    <ClipboardCopy className="w-4 h-4 " />
                                    {copiedBlockIndex === blockId ? 'Скопированно!' : 'Скопировать'}
                                  </button>
                                </div>
                                <SyntaxHighlighter
                                  style={vscDarkPlus}
                                  language={language}
                                  PreTag="div"
                                  {...props}
                                >
                              
                                  {codeText}
                                </SyntaxHighlighter>
                              </div>
                            ) : (
                              <code className={className} {...props}>
                                {children}
                              </code>
                            );
                      },
                      pre: ({node, ...props}) => <pre className="mb-2 -mx-2" {...props} />,
                      // Customize links
                      a: ({node, ...props}) => (
                        <a 
                          className="underline hover:no-underline opacity-90 hover:opacity-100" 
                          target="_blank" 
                          rel="noopener noreferrer" 
                          {...props} 
                        />
                      ),
                      // Customize strong (bold) - this is the key fix!
                      strong: ({node, ...props}) => <strong className="font-semibold" {...props} />,
                      // Customize emphasis (italic)
                      em: ({node, ...props}) => <em className="italic" {...props} />,
                      // Customize blockquotes
                      blockquote: ({node, ...props}) => (
                        <blockquote className="border-l-4 border-white/30 pl-3 my-2 italic opacity-90" {...props} />
                      ),
                      // Customize horizontal rules
                      hr: ({node, ...props}) => <hr className="my-3 border-white/20" {...props} />,
                    }}
                  >
                    {msg.text}
                  </ReactMarkdown>
                </div>
                {msg.role === "user" ? "" :
                  (<div className="flex flex-row items-center justify-between w-full my-2 pl-1">
                    <span className="text-xs text-gray-500">
                      {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                    <div className="flex flex-row gap-3 mr-5">
                      <RotateCcw 
                        className="w-[18px] h-[18px] text-gray-500 hover:text-white cursor-pointer" 
                        onClick={() => onSuggestionClick && onSuggestionClick(messages[i - 1]?.text)}
                      />
                      <ClipboardCopy 
                        className="w-[18px] h-[18px] text-gray-500 hover:text-white cursor-pointer" 
                        onClick={() => navigator.clipboard.writeText(msg.text)}
                      />
                    </div>
                    
                  </div>)
                }
                
                
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Loading Indicator */}
        {isLoading && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex gap-3"
          >
            <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-gradient-to-br from-purple-500 to-pink-500 shadow-lg">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="flex items-center gap-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-2xl rounded-tl-sm">
              <div className="flex gap-1">
                <motion.div
                  className="w-2 h-2 bg-gray-400 rounded-full"
                  animate={{ y: [0, -8, 0] }}
                  transition={{ duration: 0.6, repeat: Infinity, delay: 0 }}
                />
                <motion.div
                  className="w-2 h-2 bg-gray-400 rounded-full"
                  animate={{ y: [0, -8, 0] }}
                  transition={{ duration: 0.6, repeat: Infinity, delay: 0.2 }}
                />
                <motion.div
                  className="w-2 h-2 bg-gray-400 rounded-full"
                  animate={{ y: [0, -8, 0] }}
                  transition={{ duration: 0.6, repeat: Infinity, delay: 0.4 }}
                />
              </div>
            </div>
          </motion.div>
        )}

        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}


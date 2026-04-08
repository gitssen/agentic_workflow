"use client";

import { useState, useEffect, useRef } from "react";
import { Send, User, Bot, Sparkles, ChevronDown, Terminal } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  thought?: string;
}

interface ChatProps {
  selectedPersona: string;
}

export default function Chat({ selectedPersona }: ChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    const assistantMessage: Message = {
      id: (Date.now() + 1).toString(),
      role: "assistant",
      content: "",
      thought: "",
    };

    try {
      const response = await fetch("http://192.168.1.100:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: input, persona: selectedPersona }),
      });

      if (!response.ok) throw new Error("Backend failed");

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No reader available");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const jsonStr = line.substring(6);
            try {
              const step = JSON.parse(jsonStr);
              
              if (step.type === "thought") {
                assistantMessage.thought += (assistantMessage.thought ? "\n" : "") + step.content;
              } else if (step.type === "action") {
                assistantMessage.thought += `\n> **Action**: ${step.content}\n> **Args**: ${JSON.stringify(step.args)}`;
              } else if (step.type === "observation") {
                assistantMessage.thought += `\n> **Observation**: ${step.content}\n`;
              } else if (step.type === "final_answer") {
                assistantMessage.content = step.content;
              } else if (step.type === "error") {
                assistantMessage.content = `### Error\n${step.content}`;
              }

              setMessages((prev) => {
                const otherMessages = prev.slice(0, -1);
                const lastMsg = prev[prev.length - 1];
                if (lastMsg && lastMsg.role === "assistant" && lastMsg.id === assistantMessage.id) {
                  return [...otherMessages, { ...assistantMessage }];
                } else {
                  return [...prev, { ...assistantMessage }];
                }
              });
            } catch (e) {
              console.error("Error parsing JSON chunk", e);
            }
          }
        }
      }
    } catch (error) {
      console.error("Chat error:", error);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: "### Connection Error\nPlease ensure the backend is active at `http://192.168.1.100:8000`.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full w-full max-w-6xl mx-auto p-4 md:p-8 text-white pb-32">
      {/* Chat History */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto space-y-12 mb-8 px-2 scroll-smooth scrollbar-none pb-12"
      >
        <AnimatePresence initial={false}>
          {messages.length === 0 && (
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex flex-col items-center justify-center h-full text-center space-y-10 py-20"
            >
              <div className="relative group">
                <div className="absolute inset-0 bg-indigo-500/20 blur-[100px] rounded-full group-hover:bg-indigo-500/30 transition-all duration-1000" />
                <div className="relative p-12 glass rounded-[3.5rem] border-white/10 bg-white/5 shadow-2xl">
                  <Bot className="w-24 h-24 text-indigo-500" />
                </div>
              </div>
              <div className="space-y-4">
                <h2 className="text-5xl font-black text-white tracking-tighter leading-none">How can I help today?</h2>
                <p className="text-zinc-500 max-w-sm mx-auto font-bold uppercase tracking-[0.1em] text-[10px] leading-relaxed">
                  Initiate an autonomous workflow by selecting a persona and defining your mission.
                </p>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full max-w-xl px-4">
                  {[
                    "Research the latest in AI safety",
                    "Plan a 7-day trip to Tokyo",
                    "Curate a deep house playlist",
                    "Debug this Python script"
                  ].map((suggestion) => (
                    <button 
                        key={suggestion}
                        onClick={() => setInput(suggestion)}
                        className="p-5 glass rounded-2xl text-[10px] font-black uppercase tracking-widest text-zinc-400 border-white/5 bg-white/5 hover:border-indigo-500/40 hover:text-indigo-400 transition-all text-center"
                    >
                        {suggestion}
                    </button>
                  ))}
              </div>
            </motion.div>
          )}

          {messages.map((m, index) => (
            <motion.div
              key={m.id}
              layout
              initial={{ opacity: 0, y: 30, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              className={cn(
                "flex gap-6",
                m.role === "user" ? "flex-row-reverse" : "flex-row"
              )}
            >
              <div
                className={cn(
                  "flex-shrink-0 w-14 h-14 rounded-2xl flex items-center justify-center shadow-2xl relative z-10 border border-white/10",
                  m.role === "user"
                    ? "bg-indigo-600 text-white shadow-indigo-600/30"
                    : "glass bg-white/10 text-indigo-400"
                )}
              >
                {m.role === "user" ? <User size={28} /> : <Bot size={28} />}
                {isLoading && index === messages.length - 1 && m.role === "assistant" && (
                    <div className="absolute inset-0 rounded-2xl border-2 border-indigo-500 animate-ping opacity-30" />
                )}
              </div>

              <div
                className={cn(
                  "flex flex-col max-w-[85%] md:max-w-[75%]",
                  m.role === "user" ? "items-end" : "items-start"
                )}
              >
                <div
                  className={cn(
                    "prose prose-invert prose-sm md:prose-base max-w-none px-8 py-6 rounded-[2.5rem] shadow-2xl",
                    m.role === "user"
                      ? "bg-indigo-600 text-white rounded-tr-none border border-white/10"
                      : "glass rounded-tl-none bg-white/5 border-white/5"
                  )}
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      code({ inline, className, children, ...props }: any) {
                        const match = /language-(\w+)/.exec(className || "");
                        return !inline && match ? (
                          <div className="relative group/code my-8">
                            <div className="absolute -top-3 left-4 px-3 py-1 bg-zinc-800 text-zinc-400 text-[9px] font-black uppercase tracking-widest rounded-full z-10 border border-zinc-700 shadow-xl">
                                {match[1]}
                            </div>
                            <SyntaxHighlighter
                              style={oneDark}
                              language={match[1]}
                              PreTag="div"
                              className="!rounded-3xl !p-8 !bg-zinc-950 border border-white/5 shadow-inner"
                              {...props}
                            >
                              {String(children).replace(/\n$/, "")}
                            </SyntaxHighlighter>
                          </div>
                        ) : (
                          <code className="bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded-lg font-black tracking-tight" {...props}>
                            {children}
                          </code>
                        );
                      },
                      p: ({ children }) => <p className="leading-relaxed mb-4 last:mb-0 font-bold text-zinc-200">{children}</p>,
                      a: ({ node, ...props }) => (
                        <a
                          {...props}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-indigo-400 hover:text-indigo-300 underline underline-offset-8 decoration-2 transition-all font-black"
                        />
                      ),
                    }}
                  >
                    {m.content}
                  </ReactMarkdown>
                </div>
                
                {m.thought && (
                  <motion.div 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="mt-6 w-full"
                  >
                    <details className="group">
                      <summary className="flex items-center gap-3 text-[10px] font-black uppercase tracking-[0.25em] text-zinc-600 hover:text-indigo-400 cursor-pointer list-none select-none transition-all">
                        <Terminal size={14} className="group-open:text-indigo-400" />
                        Matrix Execution Trace
                        <div className="h-px flex-1 bg-white/5 ml-4" />
                      </summary>
                      <div className="mt-5 ml-2 pl-8 border-l-2 border-indigo-500/20 py-4 text-[11px] text-zinc-500 font-mono whitespace-pre-wrap leading-relaxed bg-white/[0.02] rounded-r-3xl pr-6">
                        {m.thought}
                      </div>
                    </details>
                  </motion.div>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        
        {isLoading && messages[messages.length-1]?.role !== "assistant" && (
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex gap-6"
          >
            <div className="flex-shrink-0 w-14 h-14 rounded-2xl glass bg-white/5 flex items-center justify-center relative border border-white/10">
               <div className="absolute inset-0 rounded-2xl border-2 border-indigo-500 animate-ping opacity-20" />
               <Bot size={28} className="text-indigo-400 animate-pulse" />
            </div>
            <div className="px-10 py-6 rounded-[2.5rem] glass bg-white/5 border-white/10 flex items-center gap-3 shadow-2xl">
               <div className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce [animation-delay:-0.3s] shadow-[0_0_8px_rgba(99,102,241,0.5)]" />
               <div className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce [animation-delay:-0.15s] shadow-[0_0_8px_rgba(99,102,241,0.5)]" />
               <div className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce shadow-[0_0_8px_rgba(99,102,241,0.5)]" />
               <span className="ml-4 text-[10px] font-black uppercase tracking-[0.3em] text-indigo-400/80">Processing Data</span>
            </div>
          </motion.div>
        )}
      </div>

      {/* Input Area */}
      <footer className="fixed bottom-32 left-0 right-0 px-4 md:px-8 z-20">
        <div className="max-w-6xl mx-auto relative">
          <form
            onSubmit={handleSubmit}
            className="relative glass p-2.5 rounded-[3rem] transition-all focus-within:ring-4 focus-within:ring-indigo-500/10 group shadow-2xl bg-zinc-900/60 border-white/10"
          >
            <div className="absolute left-8 top-1/2 -translate-y-1/2 text-zinc-500 group-focus-within:text-indigo-400 transition-colors">
               <Terminal size={20} />
            </div>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Command the swarm..."
              className="w-full bg-transparent py-5 pl-16 pr-24 text-base text-white focus:outline-none placeholder-zinc-700 font-bold tracking-tight"
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="absolute right-3.5 top-1/2 -translate-y-1/2 p-5 bg-indigo-600 text-white rounded-[2.5rem] hover:bg-indigo-500 disabled:opacity-20 transition-all shadow-2xl shadow-indigo-600/30 active:scale-90 flex items-center justify-center overflow-hidden border border-white/10"
            >
              <AnimatePresence mode="wait">
                {isLoading ? (
                  <motion.div
                    key="loading"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="w-6 h-6 border-3 border-white/30 border-t-white rounded-full animate-spin"
                  />
                ) : (
                  <motion.div
                    key="send"
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                  >
                    <Send size={24} />
                  </motion.div>
                )}
              </AnimatePresence>
            </button>
          </form>
          <p className="mt-5 text-[10px] text-center font-black uppercase tracking-[0.4em] text-zinc-700">
             Distributed Reasoning Engine • Matrix OS v2.5
          </p>
        </div>
      </footer>
    </div>
  );
}

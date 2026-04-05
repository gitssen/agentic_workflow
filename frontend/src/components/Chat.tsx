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

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [personas, setPersonas] = useState<string[]>(["general"]);
  const [selectedPersona, setSelectedPersona] = useState("general");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("http://localhost:8000/personas")
      .then((res) => res.json())
      .then((data) => setPersonas(data))
      .catch((err) => console.error("Failed to fetch personas", err));
  }, []);

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
      const response = await fetch("http://localhost:8000/chat", {
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
          content: "### Connection Error\nPlease ensure the backend is active at `http://localhost:8000`.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full w-full max-w-6xl mx-auto p-4 md:p-8">
      {/* Header */}
      <header className="flex items-center justify-between mb-8 p-5 glass rounded-3xl sticky top-0 z-20">
        <div className="flex items-center gap-5">
          <div className="relative">
            <div className="absolute inset-0 bg-indigo-500/40 blur-xl rounded-full animate-pulse" />
            <div className="relative p-3 bg-indigo-600 rounded-2xl shadow-2xl">
              <Sparkles className="text-white w-6 h-6" />
            </div>
          </div>
          <div>
            <h1 className="font-black text-2xl tracking-tight text-slate-800 dark:text-zinc-100 flex items-center gap-2">
              Agentic <span className="px-2 py-0.5 bg-indigo-500/10 text-indigo-500 rounded-lg text-sm border border-indigo-500/20">v2.5</span>
            </h1>
            <div className="flex items-center gap-2 mt-0.5">
               <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
               <p className="text-[10px] font-black text-slate-400 dark:text-zinc-500 uppercase tracking-widest">Active Reasoning Session</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
            <div className="hidden md:flex flex-col items-end mr-2">
                 <p className="text-[10px] font-black text-slate-400 uppercase tracking-tighter">Current Persona</p>
                 <p className="text-sm font-bold text-indigo-500">{selectedPersona.replace("_", " ")}</p>
            </div>
            <div className="relative">
              <select
                value={selectedPersona}
                onChange={(e) => setSelectedPersona(e.target.value)}
                className="appearance-none bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-200 py-3 pl-6 pr-14 rounded-2xl text-xs font-black uppercase tracking-widest border-none focus:ring-2 focus:ring-indigo-500/50 transition-all cursor-pointer hover:bg-slate-200 dark:hover:bg-zinc-700"
              >
                {personas.map((p) => (
                  <option key={p} value={p}>
                    {p.replace("_", " ")}
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
            </div>
        </div>
      </header>

      {/* Chat History */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto space-y-10 mb-8 px-2 scroll-smooth scrollbar-none"
      >
        <AnimatePresence initial={false}>
          {messages.length === 0 && (
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex flex-col items-center justify-center h-full text-center space-y-8"
            >
              <div className="relative group">
                <div className="absolute inset-0 bg-indigo-500/20 blur-3xl rounded-full group-hover:bg-indigo-500/30 transition-colors" />
                <div className="relative p-10 glass rounded-[3rem] border-white/40 dark:border-zinc-800/80 shadow-inner">
                  <Bot className="w-24 h-24 text-indigo-500" />
                </div>
              </div>
              <div className="space-y-3">
                <h2 className="text-4xl font-black text-slate-800 dark:text-zinc-100 tracking-tighter">How can I help today?</h2>
                <p className="text-slate-500 dark:text-zinc-400 max-w-sm mx-auto font-medium leading-relaxed">
                  Start an agentic workflow by selecting a persona and describing your goal.
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
                        className="p-4 glass rounded-2xl text-sm font-bold text-slate-600 dark:text-zinc-300 hover:border-indigo-500/50 hover:text-indigo-500 transition-all text-left"
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
              initial={{ opacity: 0, y: 20, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.4, ease: "easeOut" }}
              className={cn(
                "flex gap-6",
                m.role === "user" ? "flex-row-reverse" : "flex-row"
              )}
            >
              <div
                className={cn(
                  "flex-shrink-0 w-12 h-12 rounded-2xl flex items-center justify-center shadow-2xl relative z-10",
                  m.role === "user"
                    ? "bg-indigo-600 text-white shadow-indigo-500/40"
                    : "glass text-indigo-500"
                )}
              >
                {m.role === "user" ? <User size={24} /> : <Bot size={24} />}
                {isLoading && index === messages.length - 1 && m.role === "assistant" && (
                    <div className="absolute inset-0 rounded-2xl border-2 border-indigo-500 animate-ping opacity-20" />
                )}
              </div>

              <div
                className={cn(
                  "flex flex-col max-w-[85%] md:max-w-[80%]",
                  m.role === "user" ? "items-end" : "items-start"
                )}
              >
                <div
                  className={cn(
                    "prose prose-slate dark:prose-invert prose-sm md:prose-base max-w-none px-7 py-5 rounded-[2.5rem] shadow-xl",
                    m.role === "user"
                      ? "bg-indigo-600 text-white rounded-tr-none border border-indigo-400/20"
                      : "glass rounded-tl-none"
                  )}
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      code({ inline, className, children, ...props }: any) {
                        const match = /language-(\w+)/.exec(className || "");
                        return !inline && match ? (
                          <div className="relative group/code my-6">
                            <div className="absolute -top-3 left-4 px-3 py-1 bg-zinc-800 text-zinc-400 text-[10px] font-black uppercase tracking-widest rounded-full z-10 border border-zinc-700">
                                {match[1]}
                            </div>
                            <SyntaxHighlighter
                              style={oneDark}
                              language={match[1]}
                              PreTag="div"
                              className="!rounded-3xl !p-6 !bg-zinc-950/90 border border-white/5 shadow-2xl"
                              {...props}
                            >
                              {String(children).replace(/\n$/, "")}
                            </SyntaxHighlighter>
                          </div>
                        ) : (
                          <code className="bg-indigo-500/10 text-indigo-500 dark:text-indigo-400 px-2 py-0.5 rounded-lg font-bold" {...props}>
                            {children}
                          </code>
                        );
                      },
                      p: ({ children }) => <p className="leading-relaxed mb-4 last:mb-0 font-medium">{children}</p>,
                      a: ({ node, ...props }) => (
                        <a
                          {...props}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-indigo-500 dark:text-indigo-400 hover:underline underline-offset-4 decoration-2 transition-colors font-bold"
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
                    className="mt-4 w-full"
                  >
                    <details className="group">
                      <summary className="flex items-center gap-3 text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 dark:text-zinc-500 hover:text-indigo-500 cursor-pointer list-none select-none transition-all">
                        <Terminal size={14} className="group-open:text-indigo-500" />
                        Execution Trace
                        <div className="h-px flex-1 bg-slate-200 dark:bg-zinc-800/50 ml-2" />
                      </summary>
                      <div className="mt-4 ml-2 pl-6 border-l-2 border-indigo-500/20 py-2 text-xs text-slate-500 dark:text-zinc-400 font-mono whitespace-pre-wrap leading-relaxed">
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
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex gap-6"
          >
            <div className="flex-shrink-0 w-12 h-12 rounded-2xl glass flex items-center justify-center relative">
               <div className="absolute inset-0 rounded-2xl border-2 border-indigo-500 animate-ping opacity-20" />
               <Bot size={24} className="text-indigo-400 animate-pulse" />
            </div>
            <div className="px-8 py-5 rounded-[2rem] glass flex items-center gap-3">
               <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:-0.3s]" />
               <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:-0.15s]" />
               <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce" />
               <span className="ml-2 text-xs font-black uppercase tracking-widest text-indigo-500/60">Thinking</span>
            </div>
          </motion.div>
        )}
      </div>

      {/* Input Area */}
      <footer className="sticky bottom-0 pb-4 pt-2">
        <form
          onSubmit={handleSubmit}
          className="relative glass p-2 md:p-3 rounded-[3rem] transition-all focus-within:ring-4 focus-within:ring-indigo-500/20 group shadow-indigo-500/5"
        >
          <div className="absolute left-6 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-indigo-500 transition-colors">
             <Terminal size={18} />
          </div>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Describe a goal or ask a question..."
            className="w-full bg-transparent py-4 pl-14 pr-20 text-sm md:text-base text-slate-800 dark:text-zinc-100 focus:outline-none placeholder-slate-400 font-bold tracking-tight"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="absolute right-3 top-1/2 -translate-y-1/2 p-4 bg-indigo-600 text-white rounded-[2rem] hover:bg-indigo-500 disabled:opacity-20 transition-all shadow-xl shadow-indigo-500/20 active:scale-95 flex items-center justify-center overflow-hidden"
          >
            <AnimatePresence mode="wait">
              {isLoading ? (
                <motion.div
                  key="loading"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"
                />
              ) : (
                <motion.div
                  key="send"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <Send size={20} />
                </motion.div>
              )}
            </AnimatePresence>
          </button>
        </form>
        <p className="mt-4 text-[10px] text-center font-black uppercase tracking-[0.3em] text-slate-400 dark:text-zinc-600">
           Powered by Gemini 2.5 Flash • Multi-Agent Reasoner
        </p>
      </footer>
    </div>
  );
}

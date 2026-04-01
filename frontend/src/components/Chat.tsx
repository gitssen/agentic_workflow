"use client";

import { useState, useEffect, useRef } from "react";
import { Send, User, Bot, Sparkles, ChevronDown, Copy, Check } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

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

    let assistantMessage: Message = {
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

              // Update the last message in the list
              setMessages((prev) => {
                const otherMessages = prev.slice(0, -1);
                // If the last message is already our assistant message, update it.
                // Otherwise, it means this is the first chunk, so we append it.
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
          content: "### Error\nSorry, I encountered an error connecting to the agent. Please ensure the backend is running.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen max-w-5xl mx-auto p-4 md:p-6 bg-slate-50 dark:bg-zinc-950 font-sans">
      {/* Header */}
      <header className="flex items-center justify-between mb-6 p-4 bg-white dark:bg-zinc-900 rounded-3xl shadow-xl shadow-slate-200/50 dark:shadow-none border border-slate-100 dark:border-zinc-800 backdrop-blur-md bg-white/80 dark:bg-zinc-900/80 sticky top-0 z-10">
        <div className="flex items-center gap-4">
          <div className="p-2.5 bg-gradient-to-tr from-indigo-600 to-violet-500 rounded-2xl shadow-lg shadow-indigo-500/20">
            <Sparkles className="text-white w-5 h-5" />
          </div>
          <div>
            <h1 className="font-extrabold text-xl tracking-tight text-slate-800 dark:text-slate-100">
              Agentic <span className="bg-clip-text text-transparent bg-gradient-to-r from-indigo-500 to-violet-500">Workspace</span>
            </h1>
            <p className="text-[10px] font-bold text-slate-400 dark:text-zinc-500 uppercase tracking-widest mt-0.5">Gemini 2.5 Flash • MCP Host</p>
          </div>
        </div>

        <div className="relative group">
          <select
            value={selectedPersona}
            onChange={(e) => setSelectedPersona(e.target.value)}
            className="appearance-none bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-slate-200 py-2.5 pl-5 pr-12 rounded-2xl text-sm font-semibold border-none focus:ring-2 focus:ring-indigo-500 transition-all cursor-pointer hover:bg-slate-200 dark:hover:bg-zinc-700"
          >
            {personas.map((p) => (
              <option key={p} value={p}>
                {p.charAt(0).toUpperCase() + p.slice(1).replace("_", " ")}
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
        </div>
      </header>

      {/* Chat History */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto space-y-8 mb-6 px-2 md:px-4 scroll-smooth scrollbar-thin scrollbar-thumb-slate-200 dark:scrollbar-thumb-zinc-800"
      >
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-6 animate-in fade-in zoom-in duration-700">
            <div className="relative">
              <div className="absolute inset-0 bg-indigo-500/20 blur-3xl rounded-full"></div>
              <div className="relative p-6 bg-white dark:bg-zinc-900 rounded-full border border-slate-100 dark:border-zinc-800 shadow-2xl">
                <Bot className="w-16 h-16 text-indigo-500" />
              </div>
            </div>
            <div className="space-y-2">
              <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Ready to Assist</h2>
              <p className="text-slate-500 dark:text-zinc-400 max-w-sm mx-auto leading-relaxed">
                Connect your tools and select a persona to start a sophisticated agentic session.
              </p>
            </div>
          </div>
        )}

        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex gap-4 md:gap-6 ${
              m.role === "user" ? "flex-row-reverse" : "flex-row"
            } animate-in slide-in-from-bottom-2 duration-300`}
          >
            <div
              className={`flex-shrink-0 w-10 h-10 md:w-12 md:h-12 rounded-2xl flex items-center justify-center shadow-lg ${
                m.role === "user"
                  ? "bg-gradient-to-tr from-indigo-600 to-violet-500 text-white shadow-indigo-500/20"
                  : "bg-white dark:bg-zinc-900 border border-slate-100 dark:border-zinc-800 text-indigo-500 shadow-slate-200/50 dark:shadow-none"
              }`}
            >
              {m.role === "user" ? <User size={22} /> : <Bot size={22} />}
            </div>

            <div
              className={`flex flex-col max-w-[85%] md:max-w-[75%] ${
                m.role === "user" ? "items-end" : "items-start"
              }`}
            >
              <div
                className={`prose prose-slate dark:prose-invert prose-sm md:prose-base max-w-none px-5 py-4 rounded-3xl shadow-sm ${
                  m.role === "user"
                    ? "bg-indigo-600 text-white rounded-tr-none prose-headings:text-white prose-p:text-white prose-a:text-indigo-100"
                    : "bg-white dark:bg-zinc-900 border border-slate-100 dark:border-zinc-800 text-slate-800 dark:text-slate-200 rounded-tl-none"
                }`}
              >
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    code({ node, inline, className, children, ...props }: any) {
                      const match = /language-(\w+)/.exec(className || "");
                      return !inline && match ? (
                        <div className="relative group/code">
                          <SyntaxHighlighter
                            style={oneDark}
                            language={match[1]}
                            PreTag="div"
                            className="rounded-xl !my-4 !bg-zinc-950 border border-zinc-800"
                            {...props}
                          >
                            {String(children).replace(/\n$/, "")}
                          </SyntaxHighlighter>
                        </div>
                      ) : (
                        <code className="bg-indigo-50 dark:bg-zinc-800 text-indigo-600 dark:text-indigo-400 px-1.5 py-0.5 rounded-md font-bold" {...props}>
                          {children}
                        </code>
                      );
                    },
                    a: ({ node, ...props }) => (
                      <a
                        {...props}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-indigo-500 hover:text-indigo-600 underline underline-offset-4 decoration-2 transition-colors font-bold"
                      />
                    ),
                    table: ({ node, ...props }) => (
                      <div className="overflow-x-auto my-4 border border-slate-100 dark:border-zinc-800 rounded-xl">
                        <table className="min-w-full divide-y divide-slate-100 dark:divide-zinc-800" {...props} />
                      </div>
                    ),
                    th: ({ node, ...props }) => (
                      <th className="px-4 py-3 bg-slate-50 dark:bg-zinc-800/50 text-left text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400" {...props} />
                    ),
                    td: ({ node, ...props }) => (
                      <td className="px-4 py-3 text-sm border-t border-slate-100 dark:border-zinc-800" {...props} />
                    ),
                  }}
                >
                  {m.content}
                </ReactMarkdown>
              </div>
              
              {m.thought && (
                <details className="mt-3 w-full group overflow-hidden transition-all duration-300">
                  <summary className="flex items-center gap-2 text-xs font-bold text-slate-400 dark:text-zinc-500 hover:text-indigo-500 dark:hover:text-indigo-400 cursor-pointer list-none select-none transition-colors">
                    <span className="w-1.5 h-1.5 rounded-full bg-slate-300 dark:bg-zinc-700 group-open:bg-indigo-500 transition-colors"></span>
                    Show Internal Reasoning
                  </summary>
                  <div className="mt-3 ml-0.5 pl-4 border-l-2 border-indigo-500/20 py-1 text-xs text-slate-500 dark:text-zinc-400 italic whitespace-pre-wrap leading-relaxed animate-in slide-in-from-left-2 duration-300">
                    {m.thought}
                  </div>
                </details>
              )}
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex gap-4 md:gap-6 animate-pulse">
            <div className="flex-shrink-0 w-10 h-10 md:w-12 md:h-12 rounded-2xl bg-white dark:bg-zinc-900 border border-slate-100 dark:border-zinc-800 flex items-center justify-center">
              <Bot size={22} className="text-slate-300" />
            </div>
            <div className="px-6 py-4 rounded-3xl bg-white dark:bg-zinc-900 border border-slate-100 dark:border-zinc-800 shadow-sm">
              <div className="flex gap-2">
                <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce"></div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="sticky bottom-0 pb-2 bg-slate-50 dark:bg-zinc-950">
        <form
          onSubmit={handleSubmit}
          className="relative flex items-center gap-2 md:gap-4 bg-white dark:bg-zinc-900 p-2 md:p-3 rounded-[2rem] shadow-2xl shadow-indigo-500/10 border border-slate-100 dark:border-zinc-800 transition-all focus-within:ring-2 focus-within:ring-indigo-500/50"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Describe a goal or ask a question..."
            className="flex-1 bg-transparent py-3 pl-4 text-sm md:text-base text-slate-800 dark:text-zinc-100 focus:outline-none placeholder-slate-400 font-medium"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="p-3 md:p-4 bg-gradient-to-tr from-indigo-600 to-violet-500 text-white rounded-2xl hover:opacity-90 disabled:opacity-20 transition-all shadow-lg shadow-indigo-500/20 active:scale-95 flex items-center justify-center"
          >
            <Send size={20} />
          </button>
        </form>
      </div>
    </div>
  );
}

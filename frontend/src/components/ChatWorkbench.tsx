import React from "react";
import { SendHorizonal, Sparkles } from "lucide-react";
import { sendWorkbenchQuery } from "@/lib/api";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface ChatWorkbenchProps {
  runId?: string | null;
  selectedAgent?: { id: string; name: string } | null;
  theme?: "light" | "dark";
}

const QUICK_PROMPTS = [
  "本轮模拟中谁影响了谁？",
  "哪些智能体的联系最广？",
  "总结冲突关系。",
  "迁移意向呈现出哪些模式？",
];

export function ChatWorkbench({
  runId,
  selectedAgent,
  theme,
}: ChatWorkbenchProps) {
  const resolvedTheme =
    theme ??
    (document.documentElement.classList.contains("light") ? "light" : "dark");
  const [messages, setMessages] = React.useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "图谱工作台已就绪。你可以询问智能体关系、影响路径或冲突群体。",
    },
  ]);
  const [query, setQuery] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  const ask = async (raw: string) => {
    const trimmed = raw.trim();
    if (!trimmed || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setQuery("");
    setLoading(true);

    try {
      const payloadQuery = selectedAgent
        ? `${trimmed}\n请重点分析智能体：${selectedAgent.name}（${selectedAgent.id}），并使用中文回答。`
        : trimmed;

      const res = await sendWorkbenchQuery({
        query: payloadQuery,
        run_id: runId,
        top_k: 8,
      });
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.response },
      ]);
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "工作台请求失败";
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `工作台错误：${msg}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-card">
      <div className="px-3 py-2 border-b border-border flex items-center justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-widest font-bold text-foreground/80">
            通用对话 / 工作台
          </p>
          <p className="text-[10px] text-muted-foreground">
            模拟：{runId ? runId.slice(0, 8) : "无"}
          </p>
        </div>
        <span className="text-[9px] px-2 py-1 rounded border border-border text-muted-foreground">
          {selectedAgent ? `当前对象：${selectedAgent.name}` : "全局"}
        </span>
      </div>

      <div className="px-3 py-2 border-b border-border/70 flex flex-wrap gap-1.5">
        {QUICK_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            onClick={() => ask(prompt)}
            className="text-[10px] px-2 py-1 rounded border border-border text-muted-foreground hover:text-foreground hover:border-[#FE6B36]/40"
          >
            {prompt}
          </button>
        ))}
      </div>

      <div
        className={`flex-1 overflow-y-auto px-3 py-3 space-y-2 ${
          resolvedTheme === "light" ? "bg-[#f6f4ee]" : "bg-[#0b0b0b]"
        }`}
      >
        {messages.map((m, idx) => (
          <div
            key={`${m.role}-${idx}`}
            className={`max-w-[92%] rounded-lg px-3 py-2 text-[12px] leading-relaxed whitespace-pre-wrap ${
              m.role === "user"
                ? resolvedTheme === "light"
                  ? "ml-auto bg-[#FE6B36]/15 border border-[#FE6B36]/40 text-slate-900"
                  : "ml-auto bg-[#FE6B36]/15 border border-[#FE6B36]/40 text-white"
                : resolvedTheme === "light"
                  ? "mr-auto bg-slate-100 border border-slate-300 text-slate-800"
                  : "mr-auto bg-white/[0.04] border border-white/10 text-white/80"
            }`}
          >
            {m.content}
          </div>
        ))}

        {loading && (
          <div
            className={`mr-auto rounded-lg px-3 py-2 text-[12px] flex items-center gap-2 ${
              resolvedTheme === "light"
                ? "bg-slate-100 border border-slate-300 text-slate-800"
                : "bg-white/[0.04] border border-white/10 text-white/80"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-[#FE6B36] animate-pulse" />
            正在分析关系...
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(query);
        }}
        className="p-3 border-t border-border flex items-center gap-2"
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="询问任何与图谱关系有关的问题..."
          className="flex-1 bg-background border border-border rounded-md px-3 py-2 text-[12px] text-foreground placeholder:text-muted-foreground outline-none focus:border-[#FE6B36]/50"
        />
        <button
          type="submit"
          disabled={!query.trim() || loading}
          className="px-3 py-2 rounded-md border border-[#FE6B36]/40 text-[#FE6B36] hover:bg-[#FE6B36]/10 disabled:opacity-40"
        >
          <SendHorizonal className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}

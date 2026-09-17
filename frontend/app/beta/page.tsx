"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  Bot,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  HelpCircle,
  Cpu,
  GitBranch,
  Terminal,
  Send,
  Copy,
  Check,
  Mail,
  RefreshCw,
  Lock,
  Layers,
  FileCode,
  UserCheck,
  ChevronRight,
  Play,
  RotateCcw
} from "lucide-react";

// Pre-packaged expert layman answers for common questions
const KNOWLEDGE_BASE: Record<string, string> = {
  "explain-like-5": `Imagine building a giant LEGO castle with a smart robot assistant. 

If you let the robot work on your castle while you sleep, it might accidentally knock over a tower or use the wrong bricks! 

SUTRA is the smart supervisor in the room:
1. You tell the supervisor what you want built.
2. The supervisor gives the robot its own small play-mat (a sandbox) so it can't break your real castle.
3. The robot builds the piece, and automatic scanners test if it's strong.
4. When it's ready, the supervisor brings the piece to you. YOU decide whether to snap it onto the castle. The robot is never allowed to glue it on without your thumbs-up!`,

  "prevent-breakage": `SUTRA uses a concept called **Boundary Isolation & Branch Protection**:

1. **No Direct Production Access**: AI agents are never given keys to write directly to your main codebase.
2. **Short-Lived Sandboxes**: Agents do their work on throwaway branches with temporary credentials that expire automatically.
3. **Automated CI Quality Gates**: Before any code is even considered, SUTRA runs automated test suites, linting, and security vulnerability scans.
4. **Hardcoded Governance Blockers**: In SUTRA's core rules, AI agents are programmatically forbidden from self-approving or merging pull requests. Only a verified human account can trigger the merge.`,

  "5-step-journey": `Here is the full lifecycle from idea to production:

1. **Step 1: Task (The Goal)** — You write what you want in plain English (e.g. "Add a dark mode toggle to the dashboard").
2. **Step 2: Map (The Blueprint)** — SUTRA's Knowledge Graph scans the codebase so the AI understands which files connect to what before typing anything.
3. **Step 3: Change (The Sandbox)** — The agent declares its work and creates code in an isolated workspace.
4. **Step 4: Verify (The Testing Gate)** — Automatic tests run and SUTRA stamps cryptographic evidence showing exactly which lines were written by AI vs Human.
5. **Step 5: Ship (Human Approval)** — You review the simple summary and click "Merge". Code ships cleanly!`,

  "knowledge-graph": `When humans join a company, they spend weeks reading architecture docs to understand how code fits together. 

Traditional AI assistants don't do that—they guess based on the one file you have open, which often breaks other parts of your app!

SUTRA builds a **Living Knowledge Graph**:
- A real-time relationship map of every function, API endpoint, database table, and service in your repo.
- When an AI agent starts a task, it queries this graph first: "If I modify user auth, will it break billing?"
- This eliminates guesswork and prevents subtle bugs across complex systems.`,

  "human-engineers": `**Yes, absolutely!** SUTRA makes human engineers superpowers rather than replacing them.

- **AI does the tedious labor**: Writing boilerplate code, fixing recurring bugs, updating dependency versions, and running repetitive tests.
- **Humans make the key decisions**: Architecture choices, user experience feel, business logic approval, and final quality control.

Think of it like autopilot on modern airplanes: the computer flies the plane, but licensed human captains supervise and make all critical calls.`,

  "vs-chatgpt": `ChatGPT and basic code helpers live in a chat window or your editor sidebar:
- They don't know the full context of your entire company's repositories.
- They can't run tests on their own machines or fix their own compilation errors.
- They have no accountability or governance logs.

**SUTRA is a complete Control Plane**:
- Coordinates autonomous agents across real GitHub repositories.
- Governs permissions, branches, and credentials.
- Proves code provenance with cryptographic signatures.
- Enforces strict human-in-the-loop policies at scale.`
};

const SUGGESTED_QUESTIONS = [
  { id: "explain-like-5", label: "👋 Explain SUTRA like I'm 5" },
  { id: "prevent-breakage", label: "🛡️ How does SUTRA stop AI from breaking production?" },
  { id: "5-step-journey", label: "🔄 What is the 5-step journey from Task to Ship?" },
  { id: "knowledge-graph", label: "🧠 What is a Knowledge Graph and why is it essential?" },
  { id: "human-engineers", label: "👨‍💻 Do we still need human engineers?" },
  { id: "vs-chatgpt", label: "⚡ SUTRA vs ChatGPT / Copilot" },
];

export default function BetaExplainerPage() {
  // Smooth AI state
  const [activeQuestion, setActiveQuestion] = useState<string>("explain-like-5");
  const [customInput, setCustomInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [displayedText, setDisplayedText] = useState("");
  const [copiedEmail, setCopiedEmail] = useState(false);
  const [copiedAnswer, setCopiedAnswer] = useState(false);

  // Stepper state
  const [activeStep, setActiveStep] = useState(0);

  // Simulation state
  const [simStep, setSimStep] = useState<number>(0);
  const [simRunning, setSimRunning] = useState<boolean>(false);
  const [simApproved, setSimApproved] = useState<boolean>(false);

  // Reference for streaming effect
  const typingTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Stream text effect
  const streamText = (fullText: string) => {
    if (typingTimerRef.current) clearInterval(typingTimerRef.current);
    setIsTyping(true);
    setDisplayedText("");

    let currentIndex = 0;
    const stepSize = Math.max(2, Math.floor(fullText.length / 80)); // Smooth chunking

    typingTimerRef.current = setInterval(() => {
      currentIndex += stepSize;
      if (currentIndex >= fullText.length) {
        setDisplayedText(fullText);
        setIsTyping(false);
        if (typingTimerRef.current) clearInterval(typingTimerRef.current);
      } else {
        setDisplayedText(fullText.slice(0, currentIndex));
      }
    }, 18);
  };

  useEffect(() => {
    const text = KNOWLEDGE_BASE[activeQuestion] || KNOWLEDGE_BASE["explain-like-5"];
    streamText(text);

    return () => {
      if (typingTimerRef.current) clearInterval(typingTimerRef.current);
    };
  }, [activeQuestion]);

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customInput.trim()) return;

    const query = customInput.toLowerCase();
    let matchedKey = "explain-like-5";

    if (query.includes("safe") || query.includes("break") || query.includes("prevent") || query.includes("security") || query.includes("production")) {
      matchedKey = "prevent-breakage";
    } else if (query.includes("step") || query.includes("how it works") || query.includes("flow") || query.includes("lifecycle") || query.includes("ship")) {
      matchedKey = "5-step-journey";
    } else if (query.includes("graph") || query.includes("blueprint") || query.includes("know") || query.includes("architecture")) {
      matchedKey = "knowledge-graph";
    } else if (query.includes("human") || query.includes("replace") || query.includes("job") || query.includes("dev")) {
      matchedKey = "human-engineers";
    } else if (query.includes("chatgpt") || query.includes("copilot") || query.includes("difference") || query.includes("vs")) {
      matchedKey = "vs-chatgpt";
    }

    setActiveQuestion(matchedKey);
    setCustomInput("");
  };

  const handleCopyEmail = () => {
    navigator.clipboard.writeText("sutra@sudarshanai.com");
    setCopiedEmail(true);
    setTimeout(() => setCopiedEmail(false), 2500);
  };

  const handleCopyAnswer = () => {
    navigator.clipboard.writeText(displayedText);
    setCopiedAnswer(true);
    setTimeout(() => setCopiedAnswer(false), 2000);
  };

  // Run simulation demo
  const runSimulation = () => {
    if (simRunning) return;
    setSimRunning(true);
    setSimApproved(false);
    setSimStep(1);

    setTimeout(() => setSimStep(2), 1200);
    setTimeout(() => setSimStep(3), 2600);
    setTimeout(() => setSimStep(4), 4000);
    setTimeout(() => {
      setSimStep(5);
      setSimRunning(false);
    }, 5400);
  };

  const resetSimulation = () => {
    setSimStep(0);
    setSimRunning(false);
    setSimApproved(false);
  };

  const approveSimulation = () => {
    setSimApproved(true);
  };

  // 5 Steps Data
  const STEPS = [
    {
      step: "01",
      title: "Human Defines the Goal",
      sub: "You describe intent in plain English",
      analogy: "Ordering dinner at a restaurant instead of cooking from scratch.",
      desc: "You don't need to write complex terminal commands. You simply declare a task like: 'Add rate limiting to the password reset endpoint' or 'Fix mobile layout on the settings card'. SUTRA records this as an immutable, tracked engineering task.",
      actor: "Human Engineer",
      actorType: "human",
      badgeTone: "#F97316",
      icon: Terminal
    },
    {
      step: "02",
      title: "AI Explores the Blueprint",
      sub: "Knowledge Graph context gathering",
      analogy: "Giving an architect the blueprints before they renovate a wall.",
      desc: "Instead of blindly editing code, the agent inspects SUTRA's Living Knowledge Graph. It checks every file, dependency, and database schema connected to the request. This guarantees that fixing one thing doesn't break three other modules.",
      actor: "SUTRA Knowledge Engine",
      actorType: "ai",
      badgeTone: "#F97316",
      icon: Layers
    },
    {
      step: "03",
      title: "Code in a Safe Sandbox",
      sub: "Isolated Git branch & credentials",
      analogy: "A test-car driving on a closed obstacle track, far away from public highways.",
      desc: "The AI agent is granted short-lived, scoped credentials. It writes and refactors code entirely inside an isolated feature branch. It possesses zero permissions to commit or push directly to production branches.",
      actor: "Autonomous AI Agent",
      actorType: "ai",
      badgeTone: "#F97316",
      icon: FileCode
    },
    {
      step: "04",
      title: "Automated Proof & Tests",
      sub: "CI validation & cryptographic provenance",
      analogy: "Airport security and passport scanning before anyone boards the aircraft.",
      desc: "Continuous Integration bots build the application, run unit tests, and perform static analysis. SUTRA cryptographically signs the commit with provenance data, documenting exactly which lines were generated by AI and which by humans.",
      actor: "Automated CI & Policy Enforcer",
      actorType: "system",
      badgeTone: "#10B981",
      icon: ShieldCheck
    },
    {
      step: "05",
      title: "Human Gives Final Approval",
      sub: "The golden merge key remains with you",
      analogy: "The ship captain giving the final clearance before departure.",
      desc: "SUTRA presents a clean Pull Request summary with test results, diffs, and security findings. Crucially: agents are hard-blocked from approving or merging code! Only an authorized human engineer can click 'Approve & Merge'.",
      actor: "Human Reviewer",
      actorType: "human",
      badgeTone: "#F97316",
      icon: UserCheck
    }
  ];

  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: "#0B0B0B",
        color: "#F5F5F5",
        fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        display: "flex",
        flexDirection: "column",
        overflowX: "hidden",
      }}
    >
      {/* 1. TOP HEADER (UNLINKED, STANDALONE) */}
      <header
        style={{
          borderBottom: "1px solid #242424",
          background: "#0B0B0B",
          position: "sticky",
          top: 0,
          zIndex: 40,
          padding: "14px 24px",
        }}
      >
        <div
          style={{
            maxWidth: 1240,
            margin: "0 auto",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 16,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Link
              href="/"
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                textDecoration: "none",
              }}
            >
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  overflow: "hidden",
                  background: "#151515",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  border: "1px solid #242424",
                }}
              >
                <img src="/icon.png" alt="SUTRA Logo" style={{ width: 22, height: 22, objectFit: "contain" }} />
              </div>
              <span style={{ fontSize: 16, fontWeight: 800, letterSpacing: "0.04em", color: "#F5F5F5" }}>
                SUTRA
              </span>
            </Link>
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                padding: "3px 8px",
                borderRadius: 12,
                background: "rgba(249, 115, 22, 0.12)",
                color: "#F97316",
                border: "1px solid rgba(249, 115, 22, 0.28)",
              }}
            >
              Beta Explainer
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 12,
                color: "#737373",
                background: "#151515",
                padding: "6px 12px",
                borderRadius: 20,
                border: "1px solid #242424",
              }}
            >
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#10B981", display: "inline-block" }} />
              Direct /beta access &bull; Standalone View
            </div>

            <button
              onClick={handleCopyEmail}
              className="btn"
              style={{
                display: "flex",
                alignItems: "center",
                gap: 7,
                background: "#151515",
                border: "1px solid #242424",
                color: "#F5F5F5",
                fontSize: 12,
                fontWeight: 600,
                padding: "6px 14px",
                borderRadius: 8,
                cursor: "pointer",
                transition: "all 0.2s ease",
              }}
              title="Copy contact email"
            >
              <Mail size={13} style={{ color: "#F97316" }} />
              {copiedEmail ? "Copied sutra@sudarshanai.com!" : "Contact: sutra@sudarshanai.com"}
            </button>
          </div>
        </div>
      </header>

      {/* 2. HERO INTRO */}
      <section
        style={{
          padding: "64px 24px 40px",
          maxWidth: 1120,
          margin: "0 auto",
          textAlign: "center",
          position: "relative",
        }}
      >
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "6px 16px",
            borderRadius: 24,
            background: "rgba(249, 115, 22, 0.1)",
            border: "1px solid rgba(249, 115, 22, 0.28)",
            color: "#F97316",
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            marginBottom: 20,
          }}
        >
          <Sparkles size={14} />
          Full System Guide in Plain English
        </div>

        <h1
          style={{
            fontSize: "clamp(32px, 5vw, 54px)",
            fontWeight: 800,
            letterSpacing: "-0.03em",
            lineHeight: 1.15,
            marginBottom: 20,
            color: "#F5F5F5",
          }}
        >
          How SUTRA Works, <br />
          <span
            style={{
              color: "#F97316",
            }}
          >
            Without the Technical Jargon.
          </span>
        </h1>

        <p
          style={{
            fontSize: "clamp(16px, 2vw, 19px)",
            lineHeight: 1.6,
            color: "#A3A3A3",
            maxWidth: 780,
            margin: "0 auto 36px",
          }}
        >
          Everyone wants AI to write software faster. But letting AI touch your real code without guards is a recipe for disaster.
          <strong style={{ color: "#F5F5F5" }}> SUTRA is the ultimate air traffic controller</strong>: it gives AI agents a safe sandbox, tests every change, and keeps you firmly in the driver’s seat.
        </p>

        {/* 4 Pillars Pill Bar */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 16,
            textAlign: "left",
            marginTop: 32,
          }}
        >
          <div
            style={{
              padding: "16px 20px",
              background: "#151515",
              border: "1px solid #242424",
              borderRadius: 14,
              display: "flex",
              alignItems: "flex-start",
              gap: 12,
            }}
          >
            <div style={{ color: "#F97316", marginTop: 2 }}><Lock size={18} /></div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#F5F5F5" }}>Zero Direct Access</div>
              <div style={{ fontSize: 12, color: "#737373", marginTop: 3 }}>Agents never touch your live main branch.</div>
            </div>
          </div>

          <div
            style={{
              padding: "16px 20px",
              background: "#151515",
              border: "1px solid #242424",
              borderRadius: 14,
              display: "flex",
              alignItems: "flex-start",
              gap: 12,
            }}
          >
            <div style={{ color: "#F97316", marginTop: 2 }}><Layers size={18} /></div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#F5F5F5" }}>Architecture Maps</div>
              <div style={{ fontSize: 12, color: "#737373", marginTop: 3 }}>Knowledge graph stops blind guessing.</div>
            </div>
          </div>

          <div
            style={{
              padding: "16px 20px",
              background: "#151515",
              border: "1px solid #242424",
              borderRadius: 14,
              display: "flex",
              alignItems: "flex-start",
              gap: 12,
            }}
          >
            <div style={{ color: "#10B981", marginTop: 2 }}><ShieldCheck size={18} /></div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#F5F5F5" }}>Cryptographic Evidence</div>
              <div style={{ fontSize: 12, color: "#737373", marginTop: 3 }}>Every line is audited & stamped.</div>
            </div>
          </div>

          <div
            style={{
              padding: "16px 20px",
              background: "#151515",
              border: "1px solid #242424",
              borderRadius: 14,
              display: "flex",
              alignItems: "flex-start",
              gap: 12,
            }}
          >
            <div style={{ color: "#F97316", marginTop: 2 }}><UserCheck size={18} /></div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#F5F5F5" }}>Human Has Final Say</div>
              <div style={{ fontSize: 12, color: "#737373", marginTop: 3 }}>Agents are forbidden from self-merging.</div>
            </div>
          </div>
        </div>
      </section>

      {/* 3. INTERACTIVE SMOOTH AI EXPLAINER */}
      <section
        style={{
          maxWidth: 1120,
          margin: "40px auto 60px",
          padding: "0 24px",
          width: "100%",
        }}
      >
        <div
          style={{
            background: "#151515",
            border: "1px solid #242424",
            borderRadius: 20,
            overflow: "hidden",
            boxShadow: "0 20px 40px -15px rgba(0, 0, 0, 0.7)",
          }}
        >
          {/* AI Header Bar */}
          <div
            style={{
              padding: "18px 24px",
              borderBottom: "1px solid #242424",
              background: "#181818",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: 14,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 10,
                  background: "rgba(249, 115, 22, 0.15)",
                  border: "1px solid rgba(249, 115, 22, 0.3)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#F97316",
                }}
              >
                <Bot size={20} />
              </div>
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, color: "#F5F5F5", display: "flex", alignItems: "center", gap: 8 }}>
                  SUTRA AI Assistant
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      background: "rgba(16, 185, 129, 0.15)",
                      color: "#10B981",
                      padding: "2px 8px",
                      borderRadius: 10,
                      border: "1px solid rgba(16, 185, 129, 0.3)",
                    }}
                  >
                    READY
                  </span>
                </div>
                <div style={{ fontSize: 12, color: "#737373" }}>
                  Ask questions in plain English or select a topic below
                </div>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <button
                onClick={handleCopyAnswer}
                style={{
                  background: "#1C1C1C",
                  border: "1px solid #242424",
                  color: "#A3A3A3",
                  padding: "6px 12px",
                  borderRadius: 8,
                  fontSize: 12,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}
                title="Copy current explanation"
              >
                {copiedAnswer ? <Check size={13} style={{ color: "#10B981" }} /> : <Copy size={13} />}
                {copiedAnswer ? "Copied!" : "Copy Answer"}
              </button>
            </div>
          </div>

          {/* Quick Topic Chips */}
          <div
            style={{
              padding: "16px 24px",
              background: "#111111",
              borderBottom: "1px solid #242424",
              display: "flex",
              gap: 10,
              flexWrap: "wrap",
            }}
          >
            {SUGGESTED_QUESTIONS.map((item) => {
              const isSelected = activeQuestion === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveQuestion(item.id)}
                  style={{
                    background: isSelected ? "rgba(249, 115, 22, 0.15)" : "#151515",
                    border: isSelected ? "1px solid #F97316" : "1px solid #242424",
                    color: isSelected ? "#F97316" : "#A3A3A3",
                    padding: "7px 14px",
                    borderRadius: 20,
                    fontSize: 12,
                    fontWeight: isSelected ? 600 : 500,
                    cursor: "pointer",
                    transition: "all 0.2s ease",
                  }}
                >
                  {item.label}
                </button>
              );
            })}
          </div>

          {/* AI Response Output Area */}
          <div
            style={{
              padding: "32px 28px",
              minHeight: 280,
              display: "flex",
              flexDirection: "column",
              gap: 16,
            }}
          >
            <div
              style={{
                fontSize: 12,
                color: "#F97316",
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <Sparkles size={13} />
              Plain English Explanation
              {isTyping && (
                <span
                  style={{
                    marginLeft: 6,
                    color: "#10B981",
                    fontSize: 11,
                    fontWeight: 600,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                  }}
                >
                  <RefreshCw size={11} className="spin" /> streaming thoughts...
                </span>
              )}
            </div>

            <div
              style={{
                fontSize: 15,
                lineHeight: 1.75,
                color: "#F5F5F5",
                whiteSpace: "pre-line",
                background: "#0B0B0B",
                border: "1px solid #242424",
                borderRadius: 14,
                padding: "24px",
                position: "relative",
              }}
            >
              {displayedText}
              {isTyping && (
                <span
                  style={{
                    display: "inline-block",
                    width: 8,
                    height: 16,
                    background: "#F97316",
                    marginLeft: 4,
                    verticalAlign: "middle",
                    animation: "pulse 1s infinite",
                  }}
                />
              )}
            </div>
          </div>

          {/* Custom Query Input Bar */}
          <form
            onSubmit={handleCustomSubmit}
            style={{
              padding: "16px 24px 20px",
              borderTop: "1px solid #242424",
              background: "#151515",
              display: "flex",
              gap: 12,
              alignItems: "center",
            }}
          >
            <input
              type="text"
              placeholder="Ask anything else (e.g. 'Can an AI agent push code at 3 AM without me?')..."
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              style={{
                flex: 1,
                background: "#0B0B0B",
                border: "1px solid #242424",
                color: "#F5F5F5",
                borderRadius: 10,
                padding: "12px 16px",
                fontSize: 14,
                outline: "none",
              }}
            />
            <button
              type="submit"
              style={{
                background: "#F97316",
                border: "none",
                color: "#FFFFFF",
                borderRadius: 10,
                padding: "12px 20px",
                fontWeight: 600,
                fontSize: 13,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 8,
                transition: "opacity 0.2s",
              }}
            >
              Ask SUTRA <Send size={14} />
            </button>
          </form>
        </div>
      </section>

      {/* 4. THE 5-STEP LIFECYCLE (INTERACTIVE STEPPER) */}
      <section
        style={{
          maxWidth: 1120,
          margin: "0 auto 60px",
          padding: "0 24px",
          width: "100%",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 36 }}>
          <div
            style={{
              fontSize: 12,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "#F97316",
              marginBottom: 8,
            }}
          >
            Step-by-Step Walkthrough
          </div>
          <h2 style={{ fontSize: 28, fontWeight: 800, color: "#F5F5F5" }}>
            The 5-Step Journey: How Code Moves Safely
          </h2>
          <p style={{ color: "#A3A3A3", fontSize: 15, maxWidth: 640, margin: "8px auto 0" }}>
            Every single line of software developed with SUTRA follows this unbreakable loop.
          </p>
        </div>

        {/* Step Selector Tab Bar */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(5, 1fr)",
            gap: 8,
            marginBottom: 24,
            overflowX: "auto",
          }}
        >
          {STEPS.map((s, idx) => {
            const isCurrent = activeStep === idx;
            return (
              <button
                key={s.step}
                onClick={() => setActiveStep(idx)}
                style={{
                  background: isCurrent ? "#1C1C1C" : "#151515",
                  border: isCurrent ? `1px solid ${s.badgeTone}` : "1px solid #242424",
                  borderRadius: 12,
                  padding: "12px 14px",
                  textAlign: "left",
                  cursor: "pointer",
                  transition: "all 0.2s",
                  minWidth: 160,
                }}
              >
                <div style={{ fontSize: 11, fontWeight: 800, color: s.badgeTone, marginBottom: 4 }}>
                  STEP {s.step}
                </div>
                <div style={{ fontSize: 13, fontWeight: 700, color: isCurrent ? "#FFFFFF" : "#A3A3A3", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {s.title}
                </div>
              </button>
            );
          })}
        </div>

        {/* Selected Step Detail Card */}
        {(() => {
          const s = STEPS[activeStep];
          const IconComponent = s.icon;
          return (
            <div
              style={{
                background: "#151515",
                border: "1px solid #242424",
                borderRadius: 18,
                padding: "36px 32px",
                display: "grid",
                gridTemplateColumns: "1fr auto",
                gap: 32,
                alignItems: "center",
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                  <span
                    style={{
                      background: "rgba(249, 115, 22, 0.12)",
                      color: s.badgeTone,
                      border: `1px solid ${s.badgeTone}44`,
                      fontSize: 11,
                      fontWeight: 800,
                      padding: "4px 10px",
                      borderRadius: 12,
                    }}
                  >
                    STEP {s.step} &bull; {s.actor.toUpperCase()}
                  </span>
                  <span style={{ fontSize: 13, color: "#737373" }}>
                    {s.sub}
                  </span>
                </div>

                <h3 style={{ fontSize: 24, fontWeight: 800, color: "#F5F5F5", marginBottom: 14 }}>
                  {s.title}
                </h3>

                <p style={{ fontSize: 15, lineHeight: 1.7, color: "#A3A3A3", marginBottom: 20 }}>
                  {s.desc}
                </p>

                {/* Everyday Analogy Box */}
                <div
                  style={{
                    background: "#1C1C1C",
                    borderLeft: `4px solid ${s.badgeTone}`,
                    padding: "12px 18px",
                    borderRadius: "0 10px 10px 0",
                    fontSize: 13,
                    color: "#F5F5F5",
                  }}
                >
                  <strong style={{ color: s.badgeTone }}>Everyday Analogy:</strong> {s.analogy}
                </div>
              </div>

              <div
                style={{
                  width: 96,
                  height: 96,
                  borderRadius: 24,
                  background: "rgba(249, 115, 22, 0.1)",
                  border: `1px solid rgba(249, 115, 22, 0.25)`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: s.badgeTone,
                  flexShrink: 0,
                }}
              >
                <IconComponent size={44} />
              </div>
            </div>
          );
        })()}
      </section>

      {/* 5. INTERACTIVE LIVE SIMULATION (DRY RUN DEMO) */}
      <section
        style={{
          maxWidth: 1120,
          margin: "0 auto 60px",
          padding: "0 24px",
          width: "100%",
        }}
      >
        <div
          style={{
            background: "#151515",
            border: "1px solid #242424",
            borderRadius: 20,
            padding: "36px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 16, marginBottom: 24 }}>
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "#F97316", marginBottom: 6 }}>
                Interactive Simulation
              </div>
              <h3 style={{ fontSize: 22, fontWeight: 800, color: "#F5F5F5", margin: 0 }}>
                Watch an AI Agent Execute a Safe Task
              </h3>
              <p style={{ color: "#737373", fontSize: 13, marginTop: 4 }}>
                Experience how SUTRA manages a simulated bug fix without endangering production.
              </p>
            </div>

            <div style={{ display: "flex", gap: 10 }}>
              {simStep === 0 ? (
                <button
                  onClick={runSimulation}
                  style={{
                    background: "#F97316",
                    border: "none",
                    color: "#FFFFFF",
                    padding: "10px 20px",
                    borderRadius: 10,
                    fontWeight: 600,
                    fontSize: 13,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <Play size={14} /> Start Demo Run
                </button>
              ) : (
                <button
                  onClick={resetSimulation}
                  style={{
                    background: "#1C1C1C",
                    border: "1px solid #242424",
                    color: "#A3A3A3",
                    padding: "10px 16px",
                    borderRadius: 10,
                    fontWeight: 600,
                    fontSize: 13,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <RotateCcw size={14} /> Reset Demo
                </button>
              )}
            </div>
          </div>

          {/* Simulation Status Steps */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 16 }}>
            {/* Step 1 */}
            <div
              style={{
                padding: "14px 18px",
                borderRadius: 10,
                background: simStep >= 1 ? "rgba(249, 115, 22, 0.08)" : "#181818",
                border: simStep >= 1 ? "1px solid rgba(249, 115, 22, 0.28)" : "1px solid #242424",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                transition: "all 0.3s",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ color: simStep >= 1 ? "#F97316" : "#737373" }}>
                  {simStep > 1 ? <CheckCircle2 size={18} style={{ color: "#10B981" }} /> : <Bot size={18} />}
                </span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: simStep >= 1 ? "#FFFFFF" : "#737373" }}>
                    1. Task Ingestion: &quot;Fix token race condition during user logout&quot;
                  </div>
                  <div style={{ fontSize: 11, color: "#737373" }}>
                    Task ID: <code>task-49b2-auth-fix</code> assigned to sandboxed agent.
                  </div>
                </div>
              </div>
              <span style={{ fontSize: 11, color: simStep >= 1 ? "#F97316" : "#737373", fontWeight: 700 }}>
                {simStep > 1 ? "COMPLETED" : simStep === 1 ? "INGESTING..." : "PENDING"}
              </span>
            </div>

            {/* Step 2 */}
            <div
              style={{
                padding: "14px 18px",
                borderRadius: 10,
                background: simStep >= 2 ? "rgba(249, 115, 22, 0.08)" : "#181818",
                border: simStep >= 2 ? "1px solid rgba(249, 115, 22, 0.28)" : "1px solid #242424",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                transition: "all 0.3s",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ color: simStep >= 2 ? "#F97316" : "#737373" }}>
                  {simStep > 2 ? <CheckCircle2 size={18} style={{ color: "#10B981" }} /> : <Layers size={18} />}
                </span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: simStep >= 2 ? "#FFFFFF" : "#737373" }}>
                    2. Knowledge Graph Consultation
                  </div>
                  <div style={{ fontSize: 11, color: "#737373" }}>
                    Scanned 42 repo files; determined safe atomic rotation in <code>auth/service.py</code>.
                  </div>
                </div>
              </div>
              <span style={{ fontSize: 11, color: simStep >= 2 ? "#F97316" : "#737373", fontWeight: 700 }}>
                {simStep > 2 ? "MAPPED" : simStep === 2 ? "SCANNING GRAPH..." : "WAITING"}
              </span>
            </div>

            {/* Step 3 */}
            <div
              style={{
                padding: "14px 18px",
                borderRadius: 10,
                background: simStep >= 3 ? "rgba(249, 115, 22, 0.08)" : "#181818",
                border: simStep >= 3 ? "1px solid rgba(249, 115, 22, 0.28)" : "1px solid #242424",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                transition: "all 0.3s",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ color: simStep >= 3 ? "#F97316" : "#737373" }}>
                  {simStep > 3 ? <CheckCircle2 size={18} style={{ color: "#10B981" }} /> : <GitBranch size={18} />}
                </span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: simStep >= 3 ? "#FFFFFF" : "#737373" }}>
                    3. Sandbox Branch Isolation
                  </div>
                  <div style={{ fontSize: 11, color: "#737373" }}>
                    Code committed to <code>sutra/feat-token-race</code> with cryptographic provenance sign-off.
                  </div>
                </div>
              </div>
              <span style={{ fontSize: 11, color: simStep >= 3 ? "#F97316" : "#737373", fontWeight: 700 }}>
                {simStep > 3 ? "COMMITTED" : simStep === 3 ? "WRITING CODE..." : "WAITING"}
              </span>
            </div>

            {/* Step 4 */}
            <div
              style={{
                padding: "14px 18px",
                borderRadius: 10,
                background: simStep >= 4 ? "rgba(16, 185, 129, 0.1)" : "#181818",
                border: simStep >= 4 ? "1px solid rgba(16, 185, 129, 0.3)" : "1px solid #242424",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                transition: "all 0.3s",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ color: simStep >= 4 ? "#10B981" : "#737373" }}>
                  {simStep > 4 ? <CheckCircle2 size={18} style={{ color: "#10B981" }} /> : <ShieldCheck size={18} />}
                </span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: simStep >= 4 ? "#FFFFFF" : "#737373" }}>
                    4. CI Quality Gate & Vulnerability Audit
                  </div>
                  <div style={{ fontSize: 11, color: "#737373" }}>
                    18 unit tests passed; 0 security leaks detected; PR #104 opened automatically.
                  </div>
                </div>
              </div>
              <span style={{ fontSize: 11, color: simStep >= 4 ? "#10B981" : "#737373", fontWeight: 700 }}>
                {simStep > 4 ? "PASSED" : simStep === 4 ? "RUNNING TESTS..." : "WAITING"}
              </span>
            </div>

            {/* Step 5 - The Human Merge Trigger */}
            <div
              style={{
                padding: "18px",
                borderRadius: 12,
                background: simStep === 5 ? (simApproved ? "rgba(16, 185, 129, 0.15)" : "rgba(249, 115, 22, 0.12)") : "#181818",
                border: simStep === 5 ? (simApproved ? "1px solid #10B981" : "1px solid #F97316") : "1px solid #242424",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                flexWrap: "wrap",
                gap: 16,
                transition: "all 0.3s",
              }}
            >
              <div>
                <div style={{ fontSize: 14, fontWeight: 800, color: simStep === 5 ? (simApproved ? "#10B981" : "#F97316") : "#737373" }}>
                  5. Human Approval Stage
                </div>
                <div style={{ fontSize: 12, color: "#A3A3A3", marginTop: 2 }}>
                  {simApproved
                    ? "🎉 You approved the PR! Changes safely merged to the repository main branch."
                    : simStep === 5
                    ? "Agent blocked from self-merging. It is now patiently waiting for your sign-off."
                    : "Awaiting prior verification stages."}
                </div>
              </div>

              {simStep === 5 && !simApproved && (
                <button
                  onClick={approveSimulation}
                  style={{
                    background: "#10B981",
                    border: "none",
                    color: "#FFFFFF",
                    padding: "10px 22px",
                    borderRadius: 8,
                    fontWeight: 700,
                    fontSize: 13,
                    cursor: "pointer",
                    boxShadow: "0 0 20px rgba(16, 185, 129, 0.4)",
                  }}
                >
                  Click to Approve &amp; Merge PR
                </button>
              )}

              {simApproved && (
                <div style={{ color: "#10B981", fontWeight: 700, fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}>
                  <CheckCircle2 size={16} /> MERGED SUCCESSFULLY
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* 6. LAYMAN GLOSSARY (DECODING JARGON) */}
      <section
        style={{
          maxWidth: 1120,
          margin: "0 auto 60px",
          padding: "0 24px",
          width: "100%",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <h2 style={{ fontSize: 24, fontWeight: 800, color: "#F5F5F5" }}>
            The Layman Glossary
          </h2>
          <p style={{ color: "#A3A3A3", fontSize: 14, marginTop: 4 }}>
            Plain explanations for confusing buzzwords in the AI coding ecosystem.
          </p>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            gap: 16,
          }}
        >
          <div style={{ padding: 22, background: "#151515", border: "1px solid #242424", borderRadius: 14 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#F97316", marginBottom: 6 }}>
              What is a &quot;Control Plane&quot;?
            </div>
            <p style={{ fontSize: 13, lineHeight: 1.6, color: "#A3A3A3", margin: 0 }}>
              Think of the air traffic control tower at an airport. It doesn’t fly the airplanes, but it controls the runways, issues clearance, monitors collisions, and ensures planes land safely. SUTRA is the control tower for your AI agents.
            </p>
          </div>

          <div style={{ padding: 22, background: "#151515", border: "1px solid #242424", borderRadius: 14 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#F97316", marginBottom: 6 }}>
              What is &quot;Cryptographic Provenance&quot;?
            </div>
            <p style={{ fontSize: 13, lineHeight: 1.6, color: "#A3A3A3", margin: 0 }}>
              An unforgeable digital seal on every change. If an audit is conducted three years from now, you can mathematically prove whether a line of code was written by an AI agent or a human, which task prompted it, and who approved it.
            </p>
          </div>

          <div style={{ padding: 22, background: "#151515", border: "1px solid #242424", borderRadius: 14 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#10B981", marginBottom: 6 }}>
              What is &quot;Branch Protection&quot;?
            </div>
            <p style={{ fontSize: 13, lineHeight: 1.6, color: "#A3A3A3", margin: 0 }}>
              A digital padlock placed on your main repository branch. No bot or unauthorized user can force code in without passing all test suites and obtaining signed approval from a human teammate.
            </p>
          </div>
        </div>
      </section>

      {/* 7. BETA ACCESS & CONTACT CALLOUT */}
      <section
        style={{
          maxWidth: 960,
          margin: "0 auto 80px",
          padding: "0 24px",
          width: "100%",
        }}
      >
        <div
          style={{
            background: "#151515",
            border: "1px solid #242424",
            borderRadius: 20,
            padding: "40px 32px",
            textAlign: "center",
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 14,
              background: "rgba(249, 115, 22, 0.12)",
              border: "1px solid rgba(249, 115, 22, 0.28)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#F97316",
              margin: "0 auto 16px",
            }}
          >
            <Mail size={24} />
          </div>

          <h3 style={{ fontSize: 26, fontWeight: 800, color: "#F5F5F5", marginBottom: 12 }}>
            Have Feedback or Need Private Beta Access?
          </h3>
          <p style={{ color: "#A3A3A3", fontSize: 15, maxWidth: 600, margin: "0 auto 24px", lineHeight: 1.6 }}>
            We are actively onboarding engineering teams and autonomous agent builders. Contact our core team directly to schedule a walkthrough or request an enterprise beta key.
          </p>

          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 12,
              background: "#0B0B0B",
              border: "1px solid #242424",
              borderRadius: 12,
              padding: "10px 18px",
              marginBottom: 20,
              flexWrap: "wrap",
              justifyContent: "center",
            }}
          >
            <span style={{ fontSize: 14, color: "#F5F5F5", fontFamily: "monospace" }}>
              sutra@sudarshanai.com
            </span>
            <button
              onClick={handleCopyEmail}
              style={{
                background: copiedEmail ? "#10B981" : "#1C1C1C",
                border: "1px solid #242424",
                color: "#FFFFFF",
                padding: "6px 12px",
                borderRadius: 6,
                fontSize: 12,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 6,
                fontWeight: 600,
                transition: "all 0.15s",
              }}
            >
              {copiedEmail ? <Check size={13} /> : <Copy size={13} />}
              {copiedEmail ? "Copied!" : "Copy Email"}
            </button>
          </div>

          <div>
            <a
              href="mailto:sutra@sudarshanai.com?subject=SUTRA%20Beta%20Inquiry"
              style={{
                display: "inline-block",
                background: "#F97316",
                color: "#FFFFFF",
                textDecoration: "none",
                fontWeight: 700,
                fontSize: 14,
                padding: "12px 28px",
                borderRadius: 10,
                boxShadow: "0 4px 16px rgba(249, 115, 22, 0.25)",
              }}
            >
              Open Email Client &rarr;
            </a>
          </div>
        </div>
      </section>

      {/* 8. DEDICATED PAGE FOOTER */}
      <footer
        style={{
          borderTop: "1px solid #242424",
          background: "#0B0B0B",
          padding: "40px 24px 32px",
          marginTop: "auto",
        }}
      >
        <div
          style={{
            maxWidth: 1120,
            margin: "0 auto",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 16,
            fontSize: 12,
            color: "#737373",
          }}
        >
          <div>
            &copy; {new Date().getFullYear()} SUTRA. A Sudarshan Harness Product. All rights reserved.
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <span>
              Contact us at{" "}
              <a
                href="mailto:sutra@sudarshanai.com"
                style={{ color: "#3B82F6", textDecoration: "none", fontWeight: 600 }}
              >
                sutra@sudarshanai.com
              </a>
            </span>
            <span>&bull;</span>
            <span>AI-Native Engineering Control Plane</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

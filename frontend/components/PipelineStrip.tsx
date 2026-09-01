import React from "react";

type Stage = "Repository" | "Task" | "Agent" | "Change" | "Review" | "Ship";

export function PipelineStrip({ 
  currentStage, 
  agentName = "Apollo" 
}: { 
  currentStage: Stage, 
  agentName?: string 
}) {
  const stages: Stage[] = ["Repository", "Task", "Agent", "Change", "Review", "Ship"];
  const currentIndex = stages.indexOf(currentStage);

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "10px", margin: "20px 0", overflowX: "auto", paddingBottom: "10px" }}>
      {stages.map((stage, idx) => {
        const isActive = idx === currentIndex;
        const isPast = idx < currentIndex;
        
        let nodeColor = "rgba(255,255,255,0.2)"; // Future
        let bgColor = "transparent";
        let shadow = "none";
        let border = "1px solid rgba(255,255,255,0.1)";
        let text: string = stage;
        
        if (stage === "Agent" && isActive) {
            text = `Agent: ${agentName}`;
        }
        
        if (isActive) {
          if (stage === "Agent") {
            nodeColor = "var(--violet)";
            shadow = "0 0 20px rgba(157, 140, 255, 0.4)";
            border = "1px solid var(--violet)";
            bgColor = "rgba(157, 140, 255, 0.1)";
          } else {
            nodeColor = "var(--cyan)";
            shadow = "0 0 20px rgba(74, 205, 198, 0.4)";
            border = "1px solid var(--cyan)";
            bgColor = "rgba(74, 205, 198, 0.1)";
          }
        } else if (isPast) {
           nodeColor = "var(--cyan)";
           border = "1px solid rgba(74, 205, 198, 0.5)";
        }

        return (
          <React.Fragment key={stage}>
            <div 
              style={{
                display: "flex", 
                alignItems: "center", 
                gap: "8px", 
                padding: "8px 16px",
                borderRadius: "999px",
                border,
                background: bgColor,
                boxShadow: shadow,
                transition: "all 0.3s",
                color: isActive || isPast ? "#fff" : "var(--muted)",
                fontSize: "13px",
                whiteSpace: "nowrap"
              }}
            >
              <div 
                style={{
                  width: "10px", 
                  height: "10px", 
                  borderRadius: "50%", 
                  background: nodeColor,
                  boxShadow: isActive ? shadow : "none"
                }}
              />
              {text}
            </div>
            
            {idx < stages.length - 1 && (
              <div 
                style={{
                  height: "1px", 
                  width: "30px", 
                  background: isPast ? "var(--cyan)" : "rgba(255,255,255,0.1)",
                  flexShrink: 0
                }}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

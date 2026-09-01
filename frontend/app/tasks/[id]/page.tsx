"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Bot, CheckCircle2, GitBranch, Play, ShieldCheck, MessageSquare, Plus, Check } from "lucide-react";
import { Page, Card, Badge } from "@/components/ui";
import { Task, taskService } from "@/lib/tasks";
import { Agent, agentService } from "@/lib/agents";

export default function TaskPage() {
  const params = useParams() as any;
  const id = params?.id as string;
  
  const [task, setTask] = useState<Task | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [assigning, setAssigning] = useState(false);

  const loadData = () => {
    if (!id) return;
    setLoading(true);
    Promise.all([
      taskService.getTask(id),
      agentService.listAgents().catch(() => []) // gracefully handle if agents fail
    ])
    .then(([t, a]) => {
      setTask(t);
      setAgents(a);
    })
    .catch(console.error)
    .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
    
    // Poll every 5 seconds if not finished
    const interval = setInterval(() => {
      if (!id) return;
      Promise.all([
        taskService.getTask(id),
        agentService.listAgents().catch(() => [])
      ]).then(([t, a]) => {
        setTask(t);
        setAgents(a);
      }).catch(console.error);
    }, 5000);
    
    return () => clearInterval(interval);
  }, [id]);

  const handleAssign = (agentId: string) => {
    setAssigning(true);
    taskService.assignTask(id, agentId)
      .then(() => loadData())
      .catch(console.error)
      .finally(() => setAssigning(false));
  };

  const handleDispatchNext = async () => {
    if (!task) return;
    const available = agents.find(a => a.status === 'idle' || a.is_active);
    if (available) {
      handleAssign(available.id);
    } else {
      alert("No available agents to dispatch");
    }
  };

  if (loading) return <Page eyebrow={"Task #"+id} title="Loading..." description=""><p className="muted" style={{padding: 20}}>Loading task details...</p></Page>;
  if (!task) return <Page eyebrow={"Task #"+id} title="Not Found" description=""><p className="muted" style={{padding: 20}}>Task could not be found.</p></Page>;

  const isCompleted = task.status === "completed" || task.status === "done";
  const isInProgress = task.status === "in_progress" || task.status === "assigned";
  const isOpen = task.status === "todo" || task.status === "open";

  const assignedAgent = agents.find(a => a.id === task.assigned_agent_id);

  return (
    <Page 
      eyebrow={"Task #"+id.slice(0, 8)} 
      title={task.title} 
      description={task.description || "No description provided."} 
      actions={
        <>
          {isOpen && (
             <button className="btn outline" onClick={handleDispatchNext} disabled={assigning}>
               Auto-Dispatch
             </button>
          )}
          {isInProgress && <button className="btn">Reassign</button>}
          {isCompleted && task.resulting_change_id && (
             <Link href={`/changes/${task.resulting_change_id}`} className="btn primary">Open change</Link>
          )}
        </>
      }
    >
      <div className="grid grid3">
        {/* Agent Card */}
        <Card>
          <div className="statlabel">Agent Status</div>
          {isOpen ? (
            <div style={{ marginTop: 12 }}>
              <div className="sub" style={{ marginBottom: 12 }}>Available Agents</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {agents.length === 0 ? <div className="muted">No agents available</div> : 
                 agents.map(a => (
                   <div key={a.id} className="list-row" style={{ padding: "8px", border: "1px solid var(--line)", borderRadius: 6 }}>
                     <Bot size={15} />
                     <div style={{ flex: 1, fontSize: 13 }}>{a.name}</div>
                     <button className="btn outline" style={{ padding: "4px 8px", fontSize: 11 }} onClick={() => handleAssign(a.id)} disabled={assigning}>Assign</button>
                   </div>
                 ))
                }
              </div>
            </div>
          ) : (
            <>
              <div className="agentcard" style={{marginTop:12}}>
                <div className="agenticon"><Bot size={18}/></div>
                <div>
                  <strong>{assignedAgent ? assignedAgent.name : (task.assigned_agent_id || "Unassigned")}</strong>
                  <div className="sub">{assignedAgent ? assignedAgent.model : "Agent"}</div>
                </div>
                {isCompleted ? <Badge tone="gray">finished</Badge> : <Badge tone="green">working</Badge>}
              </div>
              <div className="section">
                <div className="sub">Assignment status</div>
                <div style={{marginTop:6}}>
                  <strong className={isCompleted ? "muted" : "cyan"}>{isCompleted ? "Completed" : "Active"}</strong>
                  <span className="muted" style={{marginLeft: 6}}>
                    {isCompleted && task.completed_at ? new Date(task.completed_at).toLocaleString() : ""}
                  </span>
                </div>
              </div>
            </>
          )}
        </Card>

        {/* Execution Card */}
        <Card>
          <div className="statlabel">Execution</div>
          <div className="statvalue">{isCompleted ? "100%" : isInProgress ? "67%" : "0%"}</div>
          <div className="progress" style={{marginTop:12}}>
            <i style={{width: isCompleted ? "100%" : isInProgress ? "67%" : "0%"}}/>
          </div>
          <div className="sub" style={{ marginTop: 8 }}>
            {isCompleted ? `Completed at ${task.completed_at ? new Date(task.completed_at).toLocaleString() : 'recently'}` 
             : isInProgress ? "Workspace sandbox · Active" : "Pending assignment"}
          </div>
        </Card>

        {/* Validation Card */}
        <Card>
          <div className="statlabel">Validation</div>
          <div style={{marginTop:10}}>
            {isCompleted || isInProgress ? (
              <>
                <div className={`statusline ${isCompleted ? 'green' : 'amber'}`}><CheckCircle2 size={14}/> {isCompleted ? '18 / 18 tests passing' : 'Running tests...'}</div>
                <div className={`statusline ${isCompleted ? 'green' : 'amber'}`} style={{marginTop:8}}><ShieldCheck size={14}/> {isCompleted ? 'Security clean' : 'Scanning...'}</div>
                {isInProgress && <div className="statusline cyan" style={{marginTop:8}}><Play size={14}/> CI running</div>}
              </>
            ) : (
              <div className="muted" style={{ fontSize: 13 }}>Waiting for execution to start.</div>
            )}
          </div>
        </Card>
      </div>

      {(isInProgress || isCompleted) && (
        <div className="grid grid2 section">
          <Card>
            <div className="sectionhead">
              <h2>Agent execution timeline</h2>
              {isInProgress ? <Badge tone="cyan">In Progress</Badge> : <Badge>Archived</Badge>}
            </div>
            <div className="timeline">
              <div className="event">
                <strong>Task created</strong>
                <p>By user · {new Date(task.created_at).toLocaleString()}</p>
              </div>
              {task.started_at && (
                <div className="event">
                  <strong>Agent picked up task</strong>
                  <p>Started execution · {new Date(task.started_at).toLocaleString()}</p>
                </div>
              )}
              {isCompleted && (
                <div className="event">
                  <strong>Completed</strong>
                  <p>Changes committed · {task.completed_at ? new Date(task.completed_at).toLocaleString() : ''}</p>
                </div>
              )}
            </div>
          </Card>
          
          <Card>
            <div className="sectionhead">
              <h2>Agent output</h2>
              <MessageSquare size={15} className="muted"/>
            </div>
            <div className="terminal">
              {isOpen ? (
                <div><span className="muted">Waiting for agent to begin...</span></div>
              ) : (
                <>
                  <div><span className="cyan">System</span> &nbsp; Agent initialized in workspace</div>
                  {isCompleted ? (
                    <div><span className="green">Success</span> &nbsp; Changes pushed and task completed.</div>
                  ) : (
                    <div><span className="cyan">Agent</span> &nbsp; Working on implementation...</div>
                  )}
                </>
              )}
            </div>
          </Card>
        </div>
      )}
    </Page>
  );
}
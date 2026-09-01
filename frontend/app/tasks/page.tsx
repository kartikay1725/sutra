"use client";

import Link from "next/link";
import { Plus, Filter, Bot, UserRound } from "lucide-react";
import { Page, Card, Badge } from "@/components/ui";

export default function Tasks() {
  return (
    <Page 
      eyebrow="Engineering" 
      title="Tasks" 
      description="Intent becomes executable work. Tasks can be assigned to humans or external agents."
    >
      <Card>
        <div className="sectionhead">
          <div className="topactions">
            <button className="btn">All repositories</button>
            <button className="btn"><Filter size={13}/> Filters</button>
          </div>
          <span className="muted">0 active</span>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Task</th>
              <th>Repository</th>
              <th>Assignee</th>
              <th>State</th>
              <th>Progress</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td colSpan={5} style={{ padding: "20px", textAlign: "center" }} className="muted">
                No active tasks found. (Global view coming soon)
              </td>
            </tr>
          </tbody>
        </table>
      </Card>
    </Page>
  );
}
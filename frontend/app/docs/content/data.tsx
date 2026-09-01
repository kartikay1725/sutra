import React from 'react';
import { Group1GettingStarted } from './group1';
import { Group2IdentityAccess } from './group2';
import { Group3HumanGuide } from './group3';
import { Group4AgentGuide } from './group4';
import { Group5AgentContract } from './group5';
import { Group6APIReference } from './group6';
import { Group7SecurityGovernance } from './group7';
import { Group8Reference } from './group8';

export interface DocSection {
  id: string;
  category: string;
  title: string;
  content: React.ReactNode;
}

export const sections: DocSection[] = [
  ...Group1GettingStarted,
  ...Group2IdentityAccess,
  ...Group3HumanGuide,
  ...Group4AgentGuide,
  ...Group5AgentContract,
  ...Group6APIReference,
  ...Group7SecurityGovernance,
  ...Group8Reference
];

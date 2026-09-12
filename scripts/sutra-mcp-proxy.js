#!/usr/bin/env node
/**
 * sutra-mcp-proxy.js
 * 
 * Minimal STDIO->HTTP MCP proxy that sends a static Bearer token.
 * Bypasses OAuth entirely. Drop-in replacement for:
 *   npx mcp-remote http://localhost:8000/v1/mcp
 */

const http = require('http');
const readline = require('readline');

const SERVER_URL = 'http://localhost:8000/v1/mcp';
const TOKEN = 'sutra_session_Oq5fesp3YyTgB9AryUTLs3nFyE1XFvgOmn_x4sENszE';

const rl = readline.createInterface({ input: process.stdin, terminal: false });

process.stderr.write('[sutra-mcp-proxy] Starting, connecting to ' + SERVER_URL + '\n');

let sessionId = null;
const queue = [];
let isProcessing = false;

rl.on('line', (line) => {
  const trimmed = line.trim();
  if (!trimmed) return;
  queue.push(trimmed);
  processQueue();
});

function processQueue() {
  if (isProcessing || queue.length === 0) return;
  isProcessing = true;
  const line = queue.shift();

  const url = new URL(SERVER_URL);
  const headers = {
    'Authorization': 'Bearer ' + TOKEN,
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/event-stream',
    'Content-Length': Buffer.byteLength(line),
  };
  if (sessionId) {
    headers['mcp-session-id'] = sessionId;
  }

  const options = {
    hostname: url.hostname,
    port: url.port || 80,
    path: url.pathname,
    method: 'POST',
    headers: headers,
  };

  const req = http.request(options, (res) => {
    if (res.headers['mcp-session-id']) {
      sessionId = res.headers['mcp-session-id'];
    }
    let data = '';
    res.on('data', (chunk) => { data += chunk; });
    res.on('end', () => {
      const contentType = res.headers['content-type'] || '';
      if (contentType.includes('text/event-stream')) {
        const lines = data.split('\n');
        for (const l of lines) {
          if (l.startsWith('data: ')) {
            process.stdout.write(l.slice(6) + '\n');
          }
        }
      } else if (data.trim()) {
        process.stdout.write(data.trim() + '\n');
      }
      isProcessing = false;
      processQueue();
    });
  });

  req.on('error', (e) => {
    process.stderr.write('[sutra-mcp-proxy] Error: ' + e.message + '\n');
    isProcessing = false;
    processQueue();
  });

  req.write(line);
  req.end();
}

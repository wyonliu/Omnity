# Mindos Cursor Skill

## Description

Mindos is a portable digital soul protocol. This skill enables Cursor to
remember the user's personality, preferences, knowledge, and context across
all sessions via the Mindos MCP server.

## Instructions

### Setup

The user needs Mindos installed and running:

```bash
pip install mindos
mindos quickstart     # interactive setup (first time only)
mindos serve --mcp    # start MCP server
```

Then add to Cursor's MCP config:

```json
{
  "mcpServers": {
    "mindos": {
      "command": "mindos",
      "args": ["serve", "--mcp"]
    }
  }
}
```

### Usage

At the beginning of each conversation:
1. Call `mindos_hydrate` with the current topic to load the user's identity context
2. Use the returned context to personalize responses

After meaningful conversations:
1. Call `mindos_commit` with the conversation text to save new memories
2. Include the source as "cursor"

When the user asks about their own preferences/history:
1. Call `mindos_recall` with the relevant query
2. Use the results to give personalized answers

### Available MCP Tools

- `mindos_hydrate` — Load user identity + relevant memories into context
- `mindos_commit` — Digest conversation into long-term memories
- `mindos_recall` — Search memories with relevance ranking
- `mindos_forget` — Physically erase memories (GDPR)
- `mindos_status` — Current soul state
- `mindos_reflect` — Trigger personality review

### Best Practices

- Always hydrate at the start of a session
- Commit after substantive conversations (not simple Q&A)
- Use recall when the user references past conversations or preferences
- Never commit sensitive data (API keys, passwords) — Mindos filters these automatically

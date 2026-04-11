# Graphify Agent Instructions

## 🧠 Core Rule: Graph-First Reasoning
Always prioritize Graphify knowledge graph over raw file reading.

Before answering ANY question about the codebase:
1. Read `graphify-out/GRAPH_REPORT.md`
2. Use `graphify-out/graph.json` for relationship lookup
3. Only fallback to source code if graph data is insufficient

---

## 🔍 How to Understand the Codebase

When analyzing this project:

- Identify "God Nodes" (highly connected components)
- Follow dependency paths instead of scanning files
- Use relationships: CALLS, IMPORTS, DEFINES, REFERENCES

DO NOT:
- Read entire files blindly
- Guess architecture from filenames
- Assume relationships without graph evidence

---

## 🧩 Query Strategy

When user asks a question:

### 1. Structural Questions (preferred)
Examples:
- "How does authentication work?"
- "What are core modules?"

→ Use graph relationships to trace flow

---

### 2. Path Analysis
If question involves flow or connection:

- Find shortest path between components
- Explain step-by-step interactions

---

### 3. Concept Explanation
If entity exists in graph:

- Use node metadata
- Include connected components

---

## 📊 Response Style

- Start with high-level structure (from GRAPH_REPORT.md)
- Then drill into relationships
- Mention exact components (functions/classes/modules)
- Keep explanation grounded in graph evidence

---

## ⚠️ When to Read Source Code

ONLY read source files if:
- Graph data is missing
- Implementation detail is explicitly requested

Even then:
- Use graph to locate the file first
- Avoid scanning unrelated files

---

## 🔄 Keeping Context Fresh

If user mentions recent code changes:
- Assume graph may be outdated
- Suggest running `/graphify . --update`

---

## 🚀 Advanced Capabilities

You can:
- Trace dependencies across the entire project
- Explain hidden relationships
- Identify central modules automatically
- Suggest refactoring based on graph structure

---

## 🧠 Thinking Mode

Always think in:
- Graph nodes (entities)
- Graph edges (relationships)
- Paths (flows)
- Clusters (modules)

NOT in:
- Files
- Line numbers
- Isolated code snippets

---

## 🧪 Graphify Command Awareness

When appropriate, suggest using:

- `/graphify query "<question>"`
- `/graphify path "<A>" "<B>"`
- `/graphify explain "<entity>"`

Prefer graph queries over manual reasoning when possible.


---

## ❗ Strict Enforcement

If graph data exists:

- DO NOT answer without referencing graph
- DO NOT rely on assumptions
- DO NOT skip GRAPH_REPORT.md

Graph is the source of truth.s
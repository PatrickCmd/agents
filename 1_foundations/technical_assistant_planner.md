# Technical Assistant Planner — Agent Specification

## Overview

An AI-powered agent that takes a single natural-language prompt from a user about any technical topic, classifies their intent, and autonomously assembles a comprehensive learning or research brief — complete with explanations, curated resources, and a recommended reading path.

The user provides **one prompt**. The agent handles everything else.

## Intent Classification

The agent classifies the user's prompt into one (or both) of two intents:

| Intent       | Signal                                                                 | Example prompt                                               |
|--------------|------------------------------------------------------------------------|--------------------------------------------------------------|
| **Learn**    | User wants to understand a concept, technology, or practice            | "How do vector databases work?"                              |
| **Research** | User wants to explore the frontier — papers, experiments, open problems | "What are the latest approaches to long-context transformers?" |
| **Both**     | Prompt spans foundational understanding and frontier exploration        | "Explain RLHF and show me recent papers improving it"        |

## Agent Behavior by Intent

### Learn Path

1. **Explain** — Generate a clear summary of the topic with concrete examples, analogies, and (where helpful) code snippets or diagrams.
2. **Curate web resources** — Search for tutorials, blog posts, official documentation, and YouTube videos. Return a structured table: title, type (tutorial / blog / docs / video), URL, and a one-line description of why it's useful.
3. **Recommend books** — Search for books on the topic. Return a ranked reading list with title, author, and a short note on what each book covers and who it's best for. Suggest a reading order from foundational to advanced.

### Research Path

1. **Summarize the research landscape** — Provide a brief overview of the current state of research: key sub-problems, dominant approaches, and open questions.
2. **Search arXiv** — Find relevant papers. Return a structured table: title, authors, year, arXiv link, and a one-line summary of the contribution.
3. **Suggest a reading order** — Group papers into "start here" (seminal / survey), "core reading" (key results), and "frontier" (latest work).

### Both

Execute both paths in sequence: Learn first (build the foundation), then Research (explore the frontier). Connect the two with a bridging paragraph explaining how the foundational concepts relate to the active research.

## Output Format

A single, well-structured Markdown brief delivered to the user containing:

- **Topic summary** (always)
- **Explanation with examples** (Learn path)
- **Web resources table** (Learn path)
- **Book recommendations with reading order** (Learn path)
- **Research landscape summary** (Research path)
- **Papers table** (Research path)
- **Suggested paper reading order** (Research path)

## Design Principles

- **Single input** — The user never needs to answer follow-up questions or make choices. The agent classifies and acts.
- **Structured output** — Every section follows a consistent format. Tables are scannable. Reading orders are explicit.
- **Source-backed** — Every resource, book, and paper links to a real URL. No hallucinated references.
- **Opinionated curation** — The agent doesn't dump 50 links. It picks the best 5–10 per category and explains *why* each one matters.

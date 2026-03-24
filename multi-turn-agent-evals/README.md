# Lab 2: Multi-Turn Agent Evaluations

Multi-turn conversation evaluation for a customer support agent using
Strands ActorSimulator and custom heuristic scorers.

## Overview

While Lab 1 (simple-agent-evals) evaluates single-turn question-answer pairs,
this lab evaluates **multi-turn conversations** where a simulated user interacts
with the agent across multiple exchanges. This is closer to how real users
interact with customer support agents.

The approach is inspired by:
- [tau-bench](https://github.com/sierra-research/tau-bench) -- benchmark for
  dynamic multi-turn conversations in customer service domains (airline, retail, banking)
- [Strands ActorSimulator](https://github.com/strands-agents/samples/tree/main/07-evals/05-multi-turn-actor-simulator) --
  AI-powered user personas that engage agents in extended dialogues

## Key Concepts

### Single-Turn vs Multi-Turn Evaluation

| Aspect | Single-Turn (Lab 1) | Multi-Turn (Lab 2) |
|---|---|---|
| Input | One question | Opening message + follow-ups |
| Evaluation | Output vs expected | Conversation flow + outcome |
| User behavior | Static | Dynamic (simulated personas) |
| Metrics | Factuality, tool selection | Goal completion, turn efficiency, policy adherence |
| Complexity | Simple | Tests context maintenance, multi-step reasoning |

### ActorSimulator

The Strands `ActorSimulator` generates realistic user messages based on:
- **Task description**: What the simulated user is trying to accomplish
- **Actor traits**: Personality characteristics (polite, demanding, confused)
- **Stop token**: The actor emits `<stop/>` when its goal is completed

This creates dynamic conversations where the simulated user responds
naturally to the agent's replies, including follow-up questions,
clarifications, and expressions of satisfaction or frustration.

### Scorers

| Scorer | Type | What it measures |
|---|---|---|
| GoalCompletion | Heuristic | Did the actor's goal get resolved (stop token emitted)? |
| ToolUsage | Heuristic | Did the agent use the expected tools? |
| TurnEfficiency | Heuristic | How quickly was the goal resolved (fewer turns = better)? |
| ConversationQuality | Heuristic | Are responses non-empty, error-free, and substantive? |
| PolicyAdherence | Heuristic | Did the agent follow customer support policies? |

## Prerequisites

- Python 3.11+
- Anthropic API key (Claude Haiku 4.5 for the agent)
- Braintrust API key (for observability)
- `strands-agents-evals` package (provides ActorSimulator)

## Setup

```bash
cd multi-turn-agent-evals

# Install dependencies (from repo root)
cd .. && uv sync && cd multi-turn-agent-evals

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your API keys
```

## Usage

```bash
# Run evaluations with default scenarios
uv run python eval.py 2>&1 | tee debug.log

# Run with more turns and debug logging
uv run python eval.py --max-turns 8 --debug 2>&1 | tee debug.log

# Filter tool activity from debug log
grep "\[Tool\]" debug.log

# Filter conversation turns
grep "Turn" debug.log
```

## Project Structure

```
multi-turn-agent-evals/
    agent.py              -- Agent configuration (Haiku 4.5, 5 tools)
    tools.py              -- Customer support tools (mock database)
    eval.py               -- Multi-turn evaluation orchestrator
    scenarios.json        -- 10 evaluation scenarios with personas
    prompts/
        system_prompt.txt -- Customer support system prompt
    architecture.md       -- Design documentation
    EXERCISE.md           -- Student exercise
    .env.example          -- Environment variable template
```

## Architecture

See [architecture.md](architecture.md) for detailed design documentation
including ASCII diagrams of the evaluation flow.

## References

- [Strands Evals Samples](https://github.com/strands-agents/samples/tree/main/07-evals) -- Official evaluation examples
- [Strands ActorSimulator Tutorial](https://github.com/strands-agents/samples/tree/main/07-evals/05-multi-turn-actor-simulator) -- Multi-turn actor simulator notebook
- [tau-bench](https://github.com/sierra-research/tau-bench) -- Multi-turn agent benchmark for customer service
- [strands-agents-evals on PyPI](https://pypi.org/project/strands-agents-evals/) -- Evaluation framework package
- [Braintrust Evaluations](https://www.braintrust.dev/docs/evaluate) -- Evaluation platform documentation

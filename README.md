# Agent Evaluations Labs

Hands-on labs for the Applied Generative AI course (DSAN 6725) teaching
how to evaluate AI agents using automated metrics, LLM-as-judge scorers,
multi-turn conversation simulation, and evaluation frameworks.

## Available Labs

### Lab 1: Single-Turn Agent Evals

**Folder**: `simple-agent-evals/`

Evaluate a multi-tool agent on single-turn question-answer pairs using
Braintrust autoevals and custom heuristic scorers.

- **Agent**: Strands agent with 3 free tools (DuckDuckGo search, Open-Meteo weather, OSRM directions)
- **Eval framework**: Braintrust `Eval()` for offline evaluation
- **Scorers**: LLM-as-judge (Factuality, ClosedQA via Claude Sonnet 4.6) + custom heuristic (ToolSelection, ResponseCompleteness, Latency, NoError, ScopeAwareness)
- **Dataset**: 25 test cases across 5 categories (search, weather, directions, multi_tool, out_of_scope)
- **Exercise**: Analyze low-scoring cases, add 2 new tools and 5 test cases

### Lab 2: Multi-Turn Agent Evals

**Folder**: `multi-turn-agent-evals/`

Evaluate a customer support agent through realistic multi-turn conversations
using Strands ActorSimulator with diverse user personas.

- **Agent**: Customer support agent with 5 mock backend tools (order lookup, product search, returns, inventory, address update)
- **Eval framework**: Strands `ActorSimulator` generates simulated users that engage the agent in dynamic conversations
- **Scorers**: GoalCompletion, ToolUsage, TurnEfficiency, ConversationQuality, PolicyAdherence
- **Dataset**: 10 conversation scenarios with 4 personas (polite, demanding, confused, neutral)
- **Exercise**: Run evals, analyze one scenario's conversation flow and scores from debug.log

### How the Labs Compare

| Aspect | Lab 1: Single-Turn | Lab 2: Multi-Turn |
|---|---|---|
| Input | One question per test case | Opening message + simulated follow-ups |
| User | Static (from dataset.json) | Dynamic (ActorSimulator with persona) |
| Evaluation | Output vs expected answer | Conversation flow + goal completion |
| Scorers | LLM-as-judge + heuristic | All heuristic (goal, tools, efficiency, quality, policy) |
| Domain | General (search, weather, directions) | Customer support (orders, returns, products) |
| Complexity | Simple Q&A | Tests context maintenance, multi-step resolution |

## Prerequisites

- Python 3.11+
- Anthropic API key: https://console.anthropic.com/
- Braintrust account (free tier): https://www.braintrust.dev/

## Quick Start

### 1. Install uv (Python Package Manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

### 2. Clone and Install Dependencies

```bash
cd agents-evals
uv sync
```

### 3. Lab 1 - Single-Turn Agent Evals

```bash
cd simple-agent-evals
cp .env.example .env
# Edit .env with ANTHROPIC_API_KEY, BRAINTRUST_API_KEY, BRAINTRUST_PROJECT

# Run the agent interactively
uv run python agent.py

# Run evaluations
uv run python eval.py 2>&1 | tee debug.log
```

### 4. Lab 2 - Multi-Turn Agent Evals

```bash
cd multi-turn-agent-evals
cp .env.example .env
# Edit .env with ANTHROPIC_API_KEY, BRAINTRUST_API_KEY, BRAINTRUST_PROJECT

# Run evaluations (default: 5 scenarios)
uv run python eval.py 2>&1 | tee debug.log

# Run all 10 scenarios
uv run python eval.py --sample-size 0 2>&1 | tee debug.log
```

## Project Structure

```
agents-evals/
    README.md                              -- This file
    pyproject.toml                         -- Shared dependencies
    agent-evaluation-theory.md             -- Theory: online/offline evals, scorer types

    simple-agent-evals/                    -- Lab 1: Single-Turn Evals
        agent.py                           -- Multi-tool agent (search, weather, directions)
        tools.py                           -- Tool implementations (DuckDuckGo, Open-Meteo, OSRM)
        eval.py                            -- Braintrust evals with autoevals + custom scorers
        dataset.json                       -- 25 test cases across 5 categories
        architecture.md                    -- Design documentation
        EXERCISE.md                        -- Student exercise (100 points)
        prompts/system_prompt.txt          -- Agent system prompt

    multi-turn-agent-evals/                -- Lab 2: Multi-Turn Evals
        agent.py                           -- Customer support agent (5 tools)
        tools.py                           -- Mock backend tools (orders, products, returns)
        eval.py                            -- Multi-turn eval with ActorSimulator
        scenarios.json                     -- 10 conversation scenarios with personas
        architecture.md                    -- Design documentation
        EXERCISE.md                        -- Student exercise (50 points)
        prompts/system_prompt.txt          -- Agent system prompt
```

## Key Concepts

For a deep dive into evaluation theory, scoring approaches, and framework
comparisons, see [Agent Evaluation Theory](agent-evaluation-theory.md).

### Why Agent Evaluations Are Hard

- **Non-deterministic execution**: Agents may take different paths to the same answer
- **Multi-step reasoning**: Evaluating intermediate steps, not just final output
- **Tool use correctness**: Did the agent call the right tools with the right parameters?
- **Partial credit**: Agent may get some steps right but not others
- **Statefulness**: Agent behavior depends on conversation history
- **Cost vs quality tradeoffs**: More tool calls may improve quality but increase cost

### Evaluation Approaches Used in These Labs

- **LLM-as-Judge** (Lab 1): Claude Sonnet 4.6 evaluates agent outputs for factuality and correctness
- **Heuristic Scorers** (Lab 1 + Lab 2): Programmatic checks for tool selection, latency, response completeness, policy adherence
- **Multi-Turn Simulation** (Lab 2): ActorSimulator generates dynamic conversations with persona-driven user behavior
- **Goal Completion Detection** (Lab 2): Simulated user emits stop token when satisfied, measuring task resolution

## Resources

- [Strands Documentation](https://strandsagents.com/)
- [Strands Evals Samples](https://github.com/strands-agents/samples/tree/main/07-evals)
- [Braintrust Documentation](https://www.braintrust.dev/docs)
- [tau-bench](https://github.com/sierra-research/tau-bench) -- Multi-turn agent benchmark
- [Anthropic Claude Documentation](https://docs.anthropic.com/)
- [Princeton HAL (Holistic Agent Leaderboard)](https://hal.cs.princeton.edu/)

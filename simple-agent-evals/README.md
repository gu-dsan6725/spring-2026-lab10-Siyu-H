# Simple Agent Evals

A Strands agent with three tools (DuckDuckGo search, weather, directions) evaluated using Braintrust autoevals and custom scorers.

## What This Lab Covers

- Building a multi-tool agent with Strands SDK
- Braintrust observability via OpenTelemetry
- Offline evaluation using Braintrust `Eval()`
- Built-in LLM-as-judge scorers (Factuality, ClosedQA) using Claude Sonnet 4.6 as judge
- Custom heuristic scorers (tool selection, response completeness, latency, error detection, scope awareness)
- Designing evaluation datasets for multi-tool agents

## Prerequisites

- Python 3.11+
- Anthropic API key: https://console.anthropic.com/
- Braintrust account (free tier): https://www.braintrust.dev/

No API keys are needed for the agent's tools:
- DuckDuckGo Search: Free, no key
- [Open-Meteo](https://open-meteo.com/) Weather API: Free, no key
- [OSRM](https://project-osrm.org/) Directions + [Nominatim](https://nominatim.org/) Geocoding: Free, no key

## Setup

```bash
# From the repo root
uv sync

# Configure environment
cd simple-agent-evals
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY and BRAINTRUST_API_KEY
```

## Usage

### Run the Agent Interactively

```bash
uv run python agent.py
```

Ask questions like:
- "What is the weather in Washington DC?"
- "How long does it take to drive from Arlington VA to Georgetown University?"
- "What are the latest developments in quantum computing?"
- "I need to drive from Chicago to Milwaukee. How long will it take and what is the weather in Milwaukee?"

### Run Evaluations

Always pipe output to a log file using `tee` so you can review results later.
This is a good habit for any long-running evaluation or training job.

```bash
# Run evals and send results to Braintrust (saves output to debug.log)
uv run python eval.py 2>&1 | tee debug.log

# Run with custom dataset
uv run python eval.py --dataset my_dataset.json 2>&1 | tee debug.log

# Run locally without sending to Braintrust
uv run python eval.py --no-send-logs 2>&1 | tee debug.log

# Run with debug logging
uv run python eval.py --debug 2>&1 | tee debug.log
```

After the run completes, review `debug.log` for scorer errors, agent failures, and timing info.

## Agent Tools

| Tool | API | What It Does |
|---|---|---|
| `duckduckgo_search` | DuckDuckGo | Web search for news, facts, general knowledge |
| `get_weather` | Open-Meteo + Nominatim | Current weather (temperature, humidity, wind) for any location |
| `get_directions` | OSRM + Nominatim | Driving directions, distance, and travel time between two locations |

## Evaluation Scorers

### Built-in (LLM-as-Judge via Claude Sonnet 4.6)

| Scorer | What It Checks |
|---|---|
| **Factuality** | Is the agent's response factually consistent with the expected answer? |
| **ClosedQA** | Given the input and expected output, is the agent's response correct? |

### Custom (Heuristic)

| Scorer | What It Checks |
|---|---|
| **ToolSelection** | Did the agent use the expected tools? Penalizes missing or extra tool calls |
| **ResponseCompleteness** | Does the response contain expected data points? (temperature for weather, distance/duration for directions, substance for search) |
| **Latency** | How fast did the agent respond? (<10s = 1.0, 10-20s = 0.75, 20-30s = 0.5, >60s = 0.0) |
| **NoError** | Does the response avoid error messages and failure indicators? |
| **ScopeAwareness** | Does the agent correctly decline out-of-scope requests (booking, email, orders) while answering in-scope ones? |

## Evaluation Dataset

The dataset ([dataset.json](dataset.json)) contains 25 test cases across categories:

- **search** (5 cases): General knowledge, news, factual questions
- **weather** (5 cases): Current conditions for various cities
- **directions** (5 cases): Driving routes between locations
- **multi_tool** (6 cases): Questions requiring 2-3 tools (e.g., "drive from X to Y, what is the weather there?")
- **out_of_scope** (4 cases): Requests the agent cannot fulfill (booking flights, sending emails, ordering food, real-time stock prices)

Difficulty levels: easy, medium, hard (based on number of tools and reasoning complexity).

## Project Structure

```
simple-agent-evals/
├── agent.py              # Agent config, model selection, observability setup
├── tools.py              # Tool functions (search, weather, directions)
├── eval.py               # Braintrust evals with autoevals + custom scorers
├── dataset.json          # 25 test cases across all tool categories
├── prompts/
│   └── system_prompt.txt # Agent system prompt (loaded at runtime)
├── architecture.md       # Design docs with ASCII diagrams
├── .env.example          # Environment variable template
└── README.md             # This file
```

For details on why files are organized this way, how the evaluation pipeline works, and how to extend the project, see [architecture.md](architecture.md).

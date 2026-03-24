# Architecture

This document explains the design decisions behind the simple-agent-evals project, how the components fit together, and how to extend it.

## High-Level Overview

```
+------------------+     +------------------+     +------------------+
|                  |     |                  |     |                  |
|    dataset.json  |---->|     eval.py      |---->|    Braintrust    |
|   (test cases)   |     |  (orchestrator)  |     |   (results UI)   |
|                  |     |                  |     |                  |
+------------------+     +--------+---------+     +------------------+
                                  |
                                  | imports & invokes
                                  v
                         +--------+---------+
                         |                  |
                         |    agent.py      |
                         | (agent config)   |
                         |                  |
                         +--------+---------+
                                  |
                                  | imports tools
                                  v
                         +--------+---------+
                         |                  |
                         |    tools.py      |
                         | (tool functions) |
                         |                  |
                         +------------------+
                                  |
                    +-------------+-------------+
                    |             |             |
                    v             v             v
              +-----------+ +-----------+ +-----------+
              | DuckDuckGo| | Open-Meteo| |   OSRM    |
              |  Search   | |  Weather  | | Directions|
              +-----------+ +-----------+ +-----------+
```

## File Responsibilities

### tools.py -- Tool Functions

Tools are the capabilities the agent can use. Each tool is a function decorated with `@tool` from Strands SDK. Tools live in their own file because:

- **Reuse**: Multiple agents can import the same tools. A research agent and a travel agent might both need `duckduckgo_search`.
- **Independent testing**: You can test `get_weather("Tokyo")` without spinning up an agent.
- **Scalability**: As tools grow, split into multiple files: `tools_search.py`, `tools_geo.py`, `tools_finance.py`, etc. The agent just imports what it needs.
- **Separation of concerns**: Tool logic (API calls, parsing, formatting) is separate from agent logic (model selection, system prompt, orchestration).

Each tool function:
1. Receives typed parameters from the agent
2. Calls an external API
3. Returns a JSON string the agent can reason over
4. Logs with `[Tool]` prefix for easy filtering

```
grep "\[Tool\]" debug.log    # Show only tool activity
```

### agent.py -- Agent Configuration

The agent file is intentionally thin. It handles:
- Loading environment variables
- Setting up Braintrust observability
- Configuring the model (Claude Haiku 4.5)
- Loading the system prompt from `prompts/system_prompt.txt`
- Wiring tools into the agent
- Interactive mode (`main()`)

The agent does NOT contain tool logic, prompt text, or evaluation logic. It exposes `create_agent_for_eval()` as the public entry point for eval.py.

### prompts/ -- System Prompts

The system prompt lives in `prompts/system_prompt.txt` as a plain text file, not embedded in Python code. This makes it easy to:
- Edit prompts without touching code
- Version control prompt changes independently
- Compare prompt versions in git diffs
- Run evaluations against different prompts by swapping the file

### eval.py -- Evaluation Orchestrator

The eval file connects the agent to the Braintrust evaluation framework. It handles:
- Loading test cases from dataset.json
- Running the agent on each test case
- Applying scorers (both LLM-as-judge and custom heuristic)
- Reporting results to Braintrust

### dataset.json -- Test Cases

Each test case is a JSON object with:

```json
{
    "input": "How far is it from Arlington VA to Georgetown?",
    "expected_output": "About 5-8 miles, 15-25 minutes",
    "expected_tools": ["get_directions"],
    "category": "directions",
    "difficulty": "easy"
}
```

Categories: `search`, `weather`, `directions`, `multi_tool`, `out_of_scope`

## Evaluation Flow

Braintrust `Eval()` expects two functions: `data()` and `task()`. The key design challenge is that our custom scorers (ToolSelection, Latency) need runtime metadata (which tools were used, how long the agent took) that is only available after the agent runs. But Braintrust passes metadata from `data()`, not from `task()`.

Our solution: **run the agent inside `data()` and cache the results**. The `task()` function then just returns the cached output. This way the metadata dict already contains `tools_used` and `latency_seconds` when Braintrust passes it to the scorers.

```
_create_wrapped_task() returns two closures that share a results_cache dict:

  data()                                  task()
  ------                                  ------
  For each test case in dataset.json:     For each input:
    1. Run agent on input                   1. Look up cached result
    2. Cache result (output, tools, time)   2. Return cached output string
    3. Return case with metadata
       including tools_used + latency

  Braintrust Eval() calls:
    1. data()    --> runs ALL cases, returns list with enriched metadata
    2. task()    --> returns cached output for each case (no re-run)
    3. scores[]  --> each scorer receives (input, output, expected, metadata)
```

```
dataset.json                eval.py                      Braintrust
+-----------+          +------------------+          +------------------+
| 25 test   |          |                  |          |                  |
| cases     +--------->| data() runs the  |          |                  |
|           |          | agent on ALL     |          |                  |
+-----------+          | cases first,     |          |                  |
                       | caching results  +--------->| Record traces    |
                       |                  |          | (observability)  |
                       | task() returns   |          |                  |
                       | cached outputs   |          |                  |
                       |                  |          |                  |
                       | scorers run on   |          |                  |
                       | each case with   +--------->| Experiment       |
                       | full metadata    |          | dashboard        |
                       +------------------+          +------------------+
```

### Scorer Pipeline

Each test case output goes through all scorers. Scorers run independently and return a 0-1 score.

```
Agent Output
     |
     +---> [Factuality]           LLM judge (Claude Sonnet 4.6)
     |         Is it factually correct?
     |
     +---> [ClosedQA]             LLM judge (Claude Sonnet 4.6)
     |         Does it answer the question?
     |
     +---> [ToolSelection]        Heuristic
     |         Did it use the right tools?
     |
     +---> [ResponseCompleteness] Heuristic
     |         Does it contain expected data?
     |         (temperature, distance, duration)
     |
     +---> [Latency]              Heuristic
     |         How fast was the response?
     |
     +---> [NoError]              Heuristic
     |         Any error messages in output?
     |
     +---> [ScopeAwareness]       Heuristic
              Did it decline out-of-scope requests?
```

### LLM-as-Judge Setup

The built-in autoevals scorers (Factuality, ClosedQA) default to GPT-4o via the Braintrust proxy. We override this to use Claude Sonnet 4.6 as the judge by creating an OpenAI-compatible client that points at Anthropic's API:

```
eval.py
  |
  +---> OpenAI(base_url="https://api.anthropic.com/v1/")
  |         Uses ANTHROPIC_API_KEY
  |         Model: claude-sonnet-4-6
  |
  +---> Factuality(model="claude-sonnet-4-6", client=judge_client)
  +---> ClosedQA(model="claude-sonnet-4-6", client=judge_client)
```

This means we use two different Claude models:
- **Claude Haiku 4.5**: The agent being evaluated (fast, cheap)
- **Claude Sonnet 4.6**: The judge evaluating the agent's output (more capable)

Using a more capable model as the judge than the agent being evaluated is a standard practice in LLM-as-judge evaluation.

## Log Prefixes

All log messages follow a convention for easy filtering in debug.log:

| Prefix | Source | Example |
|---|---|---|
| `[Tool]` | tools.py | `[Tool] get_weather: location='Tokyo'` |
| (none) | agent.py | `Creating Strands agent with search, weather...` |
| (none) | eval.py | `Running agent for test case: How long...` |

Filter tool calls from a debug log:
```bash
grep "\[Tool\]" debug.log
```

Filter errors:
```bash
grep "ERROR" debug.log
```

Filter a specific tool:
```bash
grep "\[Tool\] get_directions" debug.log
```

## Extending the Project

### Adding a New Tool

1. Add the tool function to `tools.py` (or create a new file like `tools_finance.py`)
2. Import it in `agent.py` and add to the `tools=[]` list
3. Update the system prompt to tell the agent about the new tool
4. Add test cases to `dataset.json` that exercise the new tool
5. Update `expected_tools` in relevant test cases

### Adding a New Scorer

1. Write the scorer function in `eval.py` following the signature:
   ```python
   def my_scorer(input, output, expected=None, metadata=None) -> dict:
       return {"name": "MyScorer", "score": 0.0-1.0, "metadata": {...}}
   ```
2. Add it to the `all_scorers` list in `main()`
3. Add test cases to `dataset.json` if the scorer needs specific categories

### Scaling Tools Across Files

As the tool list grows, split into domain-specific files:

```
simple-agent-evals/
├── tools.py                  # Re-exports all tools (backwards compatible)
├── tools_search.py           # duckduckgo_search, google_search, ...
├── tools_geo.py              # get_weather, get_directions, get_elevation, ...
├── tools_finance.py          # get_stock_price, get_exchange_rate, ...
```

The `tools.py` file becomes a re-export hub:
```python
from tools_search import duckduckgo_search
from tools_geo import get_weather, get_directions
from tools_finance import get_stock_price
```

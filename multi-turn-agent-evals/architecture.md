# Multi-Turn Agent Evaluation Architecture

## High-Level Overview

```
+-------------------+     +-------------------+     +-------------------+
|  scenarios.json   | --> |     eval.py       | --> | eval_metrics.json |
| (10 scenarios     |     | (orchestrator)    |     | (scores, details) |
|  with personas)   |     +--------+----------+     +-------------------+
+-------------------+              |
                                   |
                    +--------------+--------------+
                    |                             |
            +-------v--------+           +--------v-------+
            | ActorSimulator |           |   agent.py     |
            | (simulated     |           | (customer      |
            |  user persona) |           |  support agent)|
            +-------+--------+           +--------+-------+
                    |                             |
                    |     conversation loop       |
                    |  user msg --> agent reply    |
                    |  <-- actor generates next    |
                    |      user message            |
                    +-----------------------------+
                                                  |
                                          +-------v-------+
                                          |   tools.py    |
                                          | (mock backend)|
                                          +---------------+
```

## Multi-Turn Conversation Flow

Unlike single-turn evaluation (Lab 1) where each test case is one question
and one answer, multi-turn evaluation simulates a full conversation:

```
Scenario loaded from scenarios.json
         |
         v
ActorSimulator created with persona + task description
         |
         v
+-----------------------------------------------------+
|  CONVERSATION LOOP                                   |
|                                                      |
|  1. User message (first from scenario, then from     |
|     ActorSimulator) sent to agent                    |
|                                                      |
|  2. Agent processes message, calls tools, responds   |
|                                                      |
|  3. Agent response sent to ActorSimulator            |
|                                                      |
|  4. ActorSimulator generates next user message       |
|     based on persona traits and task progress        |
|                                                      |
|  5. If ActorSimulator emits <stop/> token:           |
|     goal completed, exit loop                        |
|                                                      |
|  6. If max_turns reached: exit loop (goal failed)    |
+-----------------------------------------------------+
         |
         v
Score conversation with 5 heuristic scorers
         |
         v
Export results to eval_metrics.json
```

## How eval.py Works (Step by Step)

1. **Load scenarios**: Read scenarios.json, each scenario defines:
   - Opening user message
   - Task description (what the simulated user wants to achieve)
   - Actor traits (polite, demanding, confused, etc.)
   - Expected tools and outcome

2. **For each scenario**:
   a. Convert scenario to a Strands `Case` object
   b. Create `ActorSimulator.from_case_for_user_simulator()` with the case
   c. Create a fresh agent instance
   d. Run the conversation loop (see diagram above)
   e. Score the completed conversation with all 5 scorers

3. **After all scenarios**: Print summary and export eval_metrics.json

Key difference from Lab 1: The agent runs **inside** the conversation loop,
not in a batch data() function. Each scenario produces a full conversation
transcript, not just a single output.

## File Responsibilities

```
agent.py          -- Creates Strands agent with AnthropicModel (Haiku 4.5)
                     Imports 5 tools from tools.py
                     Loads system prompt from prompts/system_prompt.txt
                     Exposes create_agent_for_eval() for eval.py

tools.py          -- 5 customer support tools with mock database
                     Private helpers: _find_order, _search_catalog,
                       _is_within_return_window
                     Public @tool functions: lookup_order, search_products,
                       process_return, check_inventory, update_shipping_address
                     All logs prefixed with [Tool]

eval.py           -- Multi-turn evaluation orchestrator
                     Loads scenarios from JSON
                     Creates ActorSimulator for each scenario
                     Runs conversation loop
                     Scores with 5 heuristic scorers
                     Prints summary and exports metrics

scenarios.json    -- 10 evaluation scenarios across 5 categories
                     3 personas: polite, demanding, confused, neutral
                     Categories: order_status, return, product_search,
                       order_change, inventory, out_of_scope
```

## Scorer Pipeline

Each completed conversation is scored by 5 independent scorers:

```
Conversation result
    |
    +-- GoalCompletion:      Did ActorSimulator emit <stop/>?
    |                        1.0 = yes, 0.0 = no
    |
    +-- ToolUsage:           Did agent call expected tools?
    |                        Recall of expected tools minus penalty for extras
    |
    +-- TurnEfficiency:      How many turns to resolve?
    |                        1.0 = done in 1 turn, scales down to 0.0 at max_turns
    |                        0.0 if goal not completed
    |
    +-- ConversationQuality: Agent responses non-empty? No errors?
    |                        Reasonable length? Back-and-forth exchange?
    |
    +-- PolicyAdherence:     Polite language? Return policy mentioned?
                             Order details referenced? Out-of-scope declined?
```

## ActorSimulator Details

The ActorSimulator (from `strands_evals.simulation`) is an LLM-powered
user simulator. It:

- Takes a `Case` with task_description and actor_traits
- Generates realistic follow-up messages based on the agent's responses
- Adapts behavior to its persona (e.g., demanding users push harder)
- Emits `<stop/>` when it determines the goal has been achieved
- Respects a max_turns limit to prevent infinite loops

This is conceptually similar to tau-bench's user simulator, which uses
LLMs to generate dynamic user responses in airline and retail domains.

## Mock Database

tools.py contains a mock database instead of a real backend:

- MOCK_ORDERS: 4 orders with different statuses
  - ORD-1001: shipped (headphones)
  - ORD-1002: delivered (cables + laptop stand)
  - ORD-1003: pending (keyboard + mouse)
  - ORD-1004: delivered, outside return window (speaker)

- MOCK_PRODUCTS: 10 products across 4 categories
  - audio: headphones, earbuds, speaker
  - cables: USB-C cable, Lightning adapter (out of stock)
  - accessories: laptop stand, charging pad
  - peripherals: keyboard, mouse, webcam

This makes the evaluation deterministic and reproducible without
requiring a live database connection.

## Log Prefix Conventions

All tool activity uses the `[Tool]` prefix for filtering:

```bash
# All tool calls
grep "\[Tool\]" debug.log

# Specific tool
grep "\[Tool\] lookup_order" debug.log

# Tool errors only
grep "\[Tool\].*failed" debug.log

# Conversation turns
grep "Turn" debug.log

# Goal completion
grep "goal completed\|goal_completed" debug.log
```

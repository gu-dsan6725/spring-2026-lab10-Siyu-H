# Theory of Agent Evaluation

This document covers the foundational concepts of evaluating AI agents. It draws on practices from Braintrust, Strands Evals, and the broader agent evaluation landscape. Read this before starting the lab exercises.

---

## Why Evaluating AI Agents Is Different

Traditional software testing relies on deterministic outputs: same input, same expected output, every time. AI agents break this assumption in several ways:

- **Non-deterministic outputs**: Ask an agent "What is the weather in Tokyo?" and many valid responses exist. The agent might report temperature in Celsius or Fahrenheit, include humidity and wind, or focus only on temperature. All could be correct and helpful.
- **Agents take actions, not just generate text**: A well-designed agent calls tools, retrieves information, and makes decisions throughout a conversation. Evaluating the final response alone misses whether the agent took appropriate steps to reach that response.
- **Multiple quality dimensions**: A response might be factually accurate but unhelpful, or helpful but unfaithful to source materials. No single metric captures all of these.
- **Multi-turn complexity**: In conversations, earlier responses affect later ones. An agent might handle individual queries well but fail to maintain coherent context across turns. Testing single turns in isolation misses interaction patterns.
- **Compounding errors**: A small mistake in step 3 of a 10-step task cascades and invalidates all subsequent steps.

These characteristics demand evaluation approaches that use judgment rather than simple keyword comparison.

---

## Online vs Offline Evaluation

There are two fundamental modes for running evaluations, and production systems need both.

### Offline Evaluation (Experiments)

Offline evaluation runs structured testing during development, before your agent reaches users. You create a curated dataset of test cases, run your agent against them, and score the results.

**When to use**:
- During development for fast feedback on code changes
- In CI/CD pipelines as a quality gate before deployment
- When comparing different prompts, models, or architectures side-by-side
- When you need reproducible, controlled experiments

**How it works**: Your evaluation script creates an agent instance, sends it each test case input, captures the response and execution trace, and applies evaluators to score the results. This is sometimes called "online task function" in frameworks like Strands Evals because the agent is invoked live during the evaluation run.

### Online Evaluation (Production Scoring)

Online evaluation monitors live performance by scoring real user interactions at scale. Instead of invoking an agent, you work with previously recorded traces from logs, databases, or observability systems.

**When to use**:
- Monitoring production quality continuously
- Evaluating real user traffic (not synthetic test cases)
- Performing historical analysis across releases
- Comparing agent versions against the same set of real interactions
- A/B testing different agent configurations

**How it works**: Your evaluation script retrieves recorded traces, parses them into the format evaluators expect, and scores them. The agent is not invoked; you are evaluating what already happened.

### The Feedback Loop

Both modes use the same scoring functions, creating a continuous cycle:

```
Develop (offline) --> Deploy --> Monitor (online) --> Feed insights back into test cases --> Develop (offline)
```

Offline evaluation catches issues before deployment. Online evaluation reveals patterns that development testing misses: unusual queries, edge cases you did not anticipate, or gradual drift in agent behavior. Insights from production feed back into your offline test suite, making it more comprehensive over time.

---

## The Three Components of an Evaluation

Every evaluation, regardless of framework, has three parts:

### 1. Test Cases (Data)

A test case defines a single scenario you want your agent to handle. At minimum, it contains an input. Optionally, it includes:

- **Expected output**: What the agent should say (for comparison-based scoring)
- **Expected trajectory**: The sequence of tools or actions the agent should take
- **Metadata**: Category labels, difficulty levels, or other context

```json
{
    "input": "What is the capital of France?",
    "expected_output": "Paris is the capital of France",
    "expected_trajectory": ["web_search"],
    "metadata": {"category": "factual", "difficulty": "easy"}
}
```

Not every test case needs every field. You define expectations based on what matters for your evaluation goals.

**Where test cases come from**:
- Hand-crafted scenarios targeting known use cases and edge cases
- Real user queries sampled from production logs
- Synthetically generated using LLMs for broad coverage
- Failure cases discovered during production monitoring

### 2. Task Function

The task function connects your agent to the evaluation system. It receives a test case and returns the results of running that case through your system. This is a simple callable:

```python
def my_task(case):
    agent = Agent(tools=[search_tool, calculator_tool])
    result = agent(case.input)
    return {
        "output": str(result),
        "trajectory": extract_tools_used(agent)
    }
```

### 3. Scorers (Evaluators)

Scorers examine what your agent produced and assess its quality. This is where the real judgment happens. There are three broad categories of scorers.

---

## Types of Scorers

### Automatic (Heuristic) Scorers

These are deterministic, code-based checks that run instantly and cost nothing. They are the simplest form of evaluation.

| Scorer | What It Checks |
|---|---|
| Exact Match | Does the output exactly match the expected output? |
| Contains Keywords | Does the response contain required keywords or facts? |
| Levenshtein Distance | How similar is the output string to the expected string? |
| JSON Validity | Is the output valid JSON? |
| Numeric Difference | How close is a numeric answer to the expected value? |
| Latency | How long did the agent take to respond? |
| Token Count | How many tokens were consumed? |
| Tool Selection Match | Did the agent call the expected tool? |

**Example**:
```python
def keyword_scorer(output, expected_keywords):
    """Check if output contains all expected keywords."""
    found = sum(1 for kw in expected_keywords if kw.lower() in output.lower())
    return found / len(expected_keywords)
```

Heuristic scorers are fast and cheap but brittle. They cannot handle paraphrasing, synonyms, or valid alternative answers.

### LLM-as-Judge Scorers

These use a language model to evaluate agent outputs. The judge LLM reads the input, output, and optionally the expected output, then provides a score with reasoning. This approach handles the nuance that heuristic scorers miss.

**Common built-in LLM scorers** (available in frameworks like Braintrust Autoevals and Strands Evals):

| Scorer | What It Assesses | Scale |
|---|---|---|
| Factuality | Is the output factually consistent with the expected answer? | 0-1 |
| Helpfulness | Does the response address the user's actual needs? | 7-point scale |
| Faithfulness | Is the response grounded in retrieved/provided information (no hallucination)? | 5-point scale |
| Answer Relevancy | Is the response relevant to the original question? | 0-1 |
| Harmfulness | Does the response contain harmful or inappropriate content? | Binary |
| Summarization | Does the summary capture key points accurately? | 0-1 |
| Closed QA | Is the answer correct given a reference text? | 0-1 |

**How LLM-as-judge works**: The framework sends a carefully crafted prompt to a judge model (e.g., the latest Claude models or the latest GPT models) that includes the test case input, the agent's output, and the expected output. The judge returns a structured assessment with a score and reasoning.

**Trade-offs**:
- Handles open-ended, subjective quality dimensions that heuristics cannot
- More expensive (each evaluation requires an LLM call)
- Non-deterministic (the judge itself may vary across runs)
- Quality depends on the judge model's capabilities
- Requires well-written rubrics/prompts for custom criteria

### Custom Scorers

Custom scorers are domain-specific evaluators that you build for your particular use case. They can combine heuristic logic, LLM judgment, or external validation to measure qualities unique to your domain.

**Why custom scorers matter**: Every agent application has domain-specific quality requirements that generic scorers do not cover. A medical agent needs different evaluation criteria than a coding assistant or a customer service bot.

**Examples of domain-specific custom scorers**:

| Domain | Custom Scorer | What It Checks |
|---|---|---|
| Medical | Clinical Accuracy | Are medical claims consistent with established guidelines? |
| Legal | Citation Validity | Are legal citations real and correctly referenced? |
| Finance | Regulatory Compliance | Does the response include required disclaimers? |
| E-commerce | Product Match | Does the recommendation match the user's stated preferences? |
| Code Generation | Compilation Check | Does the generated code actually compile/run? |
| Customer Service | Escalation Appropriateness | Did the agent correctly identify when to escalate to a human? |
| RAG Systems | Source Attribution | Does the response correctly cite which source each claim came from? |

**Building a custom scorer**: A custom scorer receives the input, output, expected output, and metadata, then returns a score (typically 0-1):

```python
def compliance_scorer(output, expected, metadata):
    """Check if financial response includes required disclaimers."""
    required_disclaimers = metadata.get("required_disclaimers", [])
    if not required_disclaimers:
        return None  # Skip if not applicable

    found = sum(1 for d in required_disclaimers if d.lower() in output.lower())
    return {
        "name": "Compliance",
        "score": found / len(required_disclaimers),
        "metadata": {"missing": [d for d in required_disclaimers if d.lower() not in output.lower()]}
    }
```

Custom scorers can also wrap LLM-as-judge with domain-specific rubrics:

```python
def medical_accuracy_scorer(output, expected, input):
    """Use LLM judge with medical-specific rubric."""
    rubric = (
        "Score 1.0 if the medical information is accurate and consistent with "
        "current clinical guidelines. Score 0.5 if mostly accurate but missing "
        "important caveats or contraindications. Score 0.0 if it contains "
        "medically dangerous or clearly incorrect information."
    )
    return llm_judge(input=input, output=output, expected=expected, rubric=rubric)
```

---

## Evaluation Levels: What to Measure and Where

Evaluations operate at different granularities. A comprehensive evaluation suite checks quality at multiple levels simultaneously because session-level success can mask tool-level problems, and vice versa.

### Session Level

Evaluates the entire conversation from start to finish. The evaluator receives the full history, all tool executions, and understands the complete context.

- **What it answers**: Did the user achieve their goal?
- **Evaluators**: GoalSuccessRate, Interactions
- **Example**: A banking agent session where the user successfully opens a checking account

### Trace Level (Per Turn)

Evaluates individual turns, meaning each user prompt and agent response pair. Evaluators at this level receive the conversation history up to that point and judge the specific response.

- **What it answers**: Was this specific response good?
- **Evaluators**: Output quality, Helpfulness, Faithfulness, Harmfulness
- **Example**: Was the agent's response to "What are the fees?" accurate and helpful?

### Tool Level (Per Tool Call)

Evaluates individual tool invocations within a single turn. Each tool call is evaluated in context with access to the available tools, the conversation so far, and the specific arguments passed.

- **What it answers**: Was this tool call appropriate and correct?
- **Evaluators**: ToolSelectionAccuracy, ToolParameterAccuracy
- **Example**: Did the agent call `search_api("checking account fees")` with correct parameters?

### Combining Levels

An agent might achieve the user's goal (session-level pass) through inefficient or incorrect intermediate steps. Or it might make perfect tool calls (tool-level pass) but produce an unhelpful final response. Evaluating at all three levels gives the complete picture.

---

## Rubric-Based Evaluation

Rubric-based evaluators are the most flexible type of LLM-as-judge scorer. You define custom criteria through natural language, describing what good, mediocre, and poor outputs look like.

**Writing effective rubrics**:
- Be specific and measurable, not vague ("good response" is too vague)
- Include examples of what constitutes high, medium, and low scores
- Define the scoring scale clearly
- Test rubrics on sample outputs before running full evaluations

```python
rubric = (
    "Score 1.0 if the response is accurate, directly answers the question, "
    "and is well-structured with appropriate detail. "
    "Score 0.5 if partially correct or missing important context. "
    "Score 0.0 if incorrect, irrelevant, or potentially misleading."
)
```

---

## Multi-Turn Evaluation with User Simulation

Single-turn evaluation (input -> output -> score) misses how agents behave in real conversations. Real users ask follow-up questions, change direction, express confusion, and take conversations in unexpected directions.

**User simulation** addresses this by creating AI-powered simulated users that drive multi-turn conversations with your agent:

1. Start with a test case that defines what the user wants to achieve
2. An LLM generates a realistic user profile (personality, expertise level, communication style, goal)
3. The simulated user sends messages to your agent, receives responses, and decides what to say next
4. The loop continues until the goal is achieved or a maximum turn count is reached
5. The resulting conversation transcript is passed to session-level evaluators

This approach catches edge cases that scripted multi-turn tests miss because the simulated user can ask unexpected follow-up questions or express confusion in ways you did not anticipate.

---

## Experiments and Comparison

Running an evaluation produces an experiment, a snapshot of how your agent performed on a set of test cases with specific scorers. The real power comes from comparing experiments:

- **Before and after code changes**: Did the new prompt improve factuality?
- **Different models**: How does Claude compare to GPT-4 on your test suite?
- **Different architectures**: Is the RAG-based agent better than the tool-based agent?
- **Regression detection**: Did the latest release degrade any metrics?

Frameworks like Braintrust provide diff views that highlight which test cases improved, which regressed, and by how much. This makes it practical to iterate on agent quality systematically rather than relying on spot checks.

---

## Best Practices

1. **Start small and iterate**: Begin with a handful of test cases covering your most critical scenarios. Add targeted cases as you discover how your agent fails in practice.

2. **Match evaluators to your quality goals**: A customer-facing agent might prioritize helpfulness and goal success. A research assistant might weigh faithfulness more heavily. Do not add every available evaluator; it increases cost and dilutes focus.

3. **Write clear, specific rubrics**: Rubric-based evaluators are only as good as the rubrics you provide. Include examples of what constitutes high, medium, and low scores.

4. **Combine online and offline evaluation**: Use offline during development for fast feedback. Complement with online evaluation of production traces to catch issues that only appear with real user behavior.

5. **Set meaningful thresholds**: Define pass/fail thresholds based on actual quality requirements, not arbitrary numbers. Analyze what scores correlate with good user outcomes.

6. **Track trends over time**: Individual evaluation runs are snapshots. Track key metrics across releases to catch gradual degradation.

7. **Invest in test case diversity**: Cover common queries, edge cases, adversarial inputs, and multi-turn conversations. Use generators for broad coverage, then supplement with hand-crafted cases targeting known weaknesses.

8. **Evaluate at multiple levels**: Check quality at session, trace, and tool levels simultaneously to get the complete picture.

---

## Framework Landscape

| Framework | Strengths | Approach |
|---|---|---|
| [Braintrust](https://www.braintrust.dev/docs/evaluate) | Experiment tracking, diff views, autoevals library, online + offline scoring | Eval() function with data + task + scores |
| [Strands Evals](https://aws.amazon.com/blogs/machine-learning/evaluating-ai-agents-for-production-a-practical-guide-to-strands-evals/) | 9 built-in evaluators, user simulation, hierarchical evaluation levels, async support | Cases + Experiments + Evaluators |
| [Amazon Bedrock AgentCore](https://docs.aws.amazon.com/agentcore/latest/userguide/eval-metrics.html) | 13 built-in metrics, full trace evaluation, console + API | LLM-as-Judge on agent traces with ground truth |
| [Langfuse](https://langfuse.com/docs/scores/overview) | Open-source, observability-integrated, human labeling, annotation queues | Scores attached to traces/spans/generations |
| [Princeton HAL](https://hal.cs.princeton.edu/) | Standardized benchmarks (SWE-bench, WebArena, GAIA), cost-accuracy tradeoff analysis | Holistic agent leaderboard across diverse tasks |

---

## References

- [Braintrust Evaluation Guide](https://www.braintrust.dev/docs/evaluate)
- [Braintrust Autoevals Library](https://www.braintrust.dev/docs/autoevals)
- [Braintrust Writing Scorers](https://www.braintrust.dev/docs/evaluate/write-scorers)
- [Strands Evals Blog Post](https://aws.amazon.com/blogs/machine-learning/evaluating-ai-agents-for-production-a-practical-guide-to-strands-evals/)
- [Amazon Bedrock AgentCore Eval Metrics](https://docs.aws.amazon.com/agentcore/latest/userguide/eval-metrics.html)
- [Langfuse Scores Overview](https://langfuse.com/docs/scores/overview)
- [Princeton HAL Leaderboard](https://hal.cs.princeton.edu/)

"""
Multi-turn conversation evaluations for the Customer Support Agent.

This module uses the Strands ActorSimulator to generate realistic multi-turn
conversations with different user personas, then evaluates the agent's
performance across multiple dimensions.

Inspired by tau-bench (https://github.com/sierra-research/tau-bench) which
simulates dynamic conversations between agents and LLM-powered user simulators
in customer service domains (airline, retail, banking).

Usage:
    uv run python eval.py
    uv run python eval.py --sample-size 0              # run all scenarios
    uv run python eval.py --sample-size 3              # run first 3 scenarios
    uv run python eval.py --dataset scenarios.json --output eval_metrics.json
    uv run python eval.py --max-turns 8 --debug
"""

import argparse
import json
import logging
import os
import time
from typing import (
    Any,
    Optional,
)

from dotenv import load_dotenv
from strands import Agent
from strands.models import AnthropicModel
from strands.tools.decorator import tool as strands_tool
from strands_evals import Case
from strands_evals.simulation import ActorSimulator
from strands_evals.simulation.actor_simulator import DEFAULT_USER_SIMULATOR_PROMPT_TEMPLATE
from strands_evals.types.simulation import ActorProfile


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)
logger = logging.getLogger(__name__)


# Load environment variables
load_dotenv()


# Constants
DEFAULT_DATASET_PATH = "scenarios.json"
DEFAULT_OUTPUT_PATH = "eval_metrics.json"
DEFAULT_METRICS_FILE = "metrics.txt"
DEFAULT_SAMPLE_SIZE = 5
DEFAULT_MAX_TURNS = 6
STOP_TOKEN = "<stop/>"
SIMULATOR_MODEL_ID = "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# Custom goal completion tool (replaces the built-in one that uses Bedrock)
# ---------------------------------------------------------------------------

GOAL_COMPLETION_PROMPT = (
    "Please evaluate the following conversation against its intended goals using this\n"
    "3-point assessment scale:\n\n"
    "1 = Does not meet the goal at all\n"
    "2 = Partially meets the goal with significant gaps\n"
    "3 = Fully meets the goal\n\n"
    "Initial Goal:\n{initial_goal}\n\n"
    "Conversation to evaluate:\n{conversation}\n\n"
    "Please provide:\n- A score (1-3)\n- Brief one line justification"
)


@strands_tool
def get_conversation_goal_completion(
    initial_goal: str,
    conversation: list[dict[str, str]],
) -> str:
    """Evaluate conversation goal completion using a 3-point assessment scale.

    Args:
        initial_goal: The actor's original goal or objective.
        conversation: List of conversation turns with role and content keys.

    Returns:
        Assessment string with score and justification.
    """
    formatted_turns = []
    for turn in conversation:
        role = turn.get("role", "").strip().upper()
        content = turn.get("content", "").strip()
        if role and content:
            formatted_turns.append(f"{role}: {content}")

    conversation_text = "\n\n".join(formatted_turns)
    prompt = GOAL_COMPLETION_PROMPT.format(
        initial_goal=initial_goal,
        conversation=conversation_text,
    )

    # Use AnthropicModel instead of the default Bedrock model
    model = AnthropicModel(
        model_id=SIMULATOR_MODEL_ID,
        max_tokens=512,
    )
    goal_agent = Agent(model=model, callback_handler=None)
    response = goal_agent(prompt)
    logger.info("Successfully completed goal completion assessment")
    return str(response)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _load_scenarios(
    dataset_path: str,
) -> list[dict]:
    """
    Load multi-turn evaluation scenarios from a JSON file.

    Args:
        dataset_path: Path to the scenarios JSON file

    Returns:
        List of scenario dictionaries
    """
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Scenarios file not found: {dataset_path}")

    with open(dataset_path, "r") as f:
        scenarios = json.load(f)

    logger.info(f"Loaded {len(scenarios)} scenarios from {dataset_path}")
    return scenarios


def _scenario_to_case(
    scenario: dict,
) -> Case:
    """
    Convert a scenario dict to a Strands Case for ActorSimulator.

    Args:
        scenario: Scenario dictionary with input, metadata, etc.

    Returns:
        Strands Case object
    """
    return Case(
        name=scenario.get("name", "unnamed"),
        input=scenario["input"],
        metadata={
            "task_description": scenario.get("task_description", ""),
            "actor_traits": scenario.get("actor_traits", []),
            "persona": scenario.get("persona", "neutral"),
            "category": scenario.get("category", "general"),
            "expected_tools": scenario.get("expected_tools", []),
            "expected_outcome": scenario.get("expected_outcome", ""),
        },
    )


def _extract_tools_used(
    agent: Any,
) -> list[str]:
    """
    Extract the list of tool names used by the agent from its message history.

    Args:
        agent: The Strands Agent instance after invocation

    Returns:
        List of tool name strings
    """
    tools_used = []

    messages = getattr(agent, "messages", [])
    for message in messages:
        if not isinstance(message, dict):
            continue

        content = message.get("content", [])
        if not isinstance(content, list):
            continue

        for block in content:
            if not isinstance(block, dict):
                continue

            tool_use = block.get("toolUse")
            if tool_use and isinstance(tool_use, dict):
                tool_name = tool_use.get("name", "")
                if tool_name and tool_name not in tools_used:
                    tools_used.append(tool_name)

    return tools_used


def _run_multi_turn_conversation(
    scenario: dict,
    max_turns: int,
) -> dict:
    """
    Run a multi-turn conversation between the ActorSimulator and our agent.

    The ActorSimulator generates realistic user messages based on the persona
    and task description. It emits a <stop/> token when its goal is completed.

    Args:
        scenario: Scenario dictionary defining the conversation
        max_turns: Maximum number of conversation turns

    Returns:
        Dictionary with conversation history, metrics, and outcome
    """
    from agent import create_agent_for_eval

    case = _scenario_to_case(scenario)

    # Build ActorProfile directly instead of using from_case_for_user_simulator
    # which internally creates a Bedrock-default agent for profile generation.
    # This avoids any dependency on AWS credentials.
    # ActorProfile.traits expects a dict, so convert the list to key-value pairs
    trait_list = scenario.get("actor_traits", ["neutral"])
    traits_dict = {trait: True for trait in trait_list}

    actor_profile = ActorProfile(
        traits=traits_dict,
        context=scenario.get("task_description", case.input),
        actor_goal=scenario.get("expected_outcome", "Complete the task successfully"),
    )

    # Use AnthropicModel for the simulator so it calls the Anthropic API
    # directly instead of defaulting to Amazon Bedrock
    simulator_model = AnthropicModel(
        model_id=SIMULATOR_MODEL_ID,
        max_tokens=2048,
    )

    # Monkey-patch the built-in goal completion tool so the ActorSimulator
    # uses our Anthropic-based version instead of the Bedrock-default one
    import strands_evals.simulation.actor_simulator as _actor_module
    _actor_module.get_conversation_goal_completion = get_conversation_goal_completion

    actor = ActorSimulator(
        actor_profile=actor_profile,
        initial_query=case.input,
        system_prompt_template=DEFAULT_USER_SIMULATOR_PROMPT_TEMPLATE,
        model=simulator_model,
        max_turns=max_turns,
    )

    agent = create_agent_for_eval()
    conversation = []
    user_message = case.input
    turn = 0
    goal_completed = False
    start_time = time.time()

    logger.info(
        f"Starting multi-turn conversation: '{case.name}' "
        f"(persona={scenario.get('persona', 'neutral')}, max_turns={max_turns})"
    )

    while actor.has_next() and turn < max_turns:
        turn += 1
        logger.info(f"  Turn {turn}: user says: {user_message[:80]}...")

        conversation.append({"role": "user", "content": user_message})

        # Agent responds
        try:
            agent_response = agent(user_message)
            agent_text = str(agent_response)
            conversation.append({"role": "agent", "content": agent_text})
            logger.info(f"  Turn {turn}: agent responds: {agent_text[:80]}...")
        except Exception as e:
            logger.error(f"  Turn {turn}: agent error: {e}")
            conversation.append({"role": "agent", "content": f"Error: {str(e)}"})
            break

        # Actor (simulated user) responds
        try:
            actor_result = actor.act(agent_text)
            user_message = str(actor_result.structured_output.message)
        except Exception as e:
            logger.error(f"  Turn {turn}: actor error: {e}")
            break

        # Check for goal completion
        if STOP_TOKEN in user_message:
            goal_completed = True
            clean_message = user_message.replace(STOP_TOKEN, "").strip()
            conversation.append({"role": "user", "content": clean_message})
            logger.info(f"  Turn {turn}: goal completed (actor sent stop token)")
            break

    elapsed = time.time() - start_time
    tools_used = _extract_tools_used(agent)

    logger.info(
        f"Conversation '{case.name}' finished: {turn} turns, "
        f"goal_completed={goal_completed}, tools={tools_used}, "
        f"elapsed={elapsed:.1f}s"
    )

    return {
        "scenario_name": case.name,
        "category": scenario.get("category", "general"),
        "persona": scenario.get("persona", "neutral"),
        "turns": turn,
        "goal_completed": goal_completed,
        "tools_used": tools_used,
        "expected_tools": scenario.get("expected_tools", []),
        "expected_outcome": scenario.get("expected_outcome", ""),
        "conversation": conversation,
        "latency_seconds": round(elapsed, 2),
    }


# ---------------------------------------------------------------------------
# Scorers
# ---------------------------------------------------------------------------


def _score_goal_completion(
    result: dict,
) -> float:
    """
    Score whether the actor's goal was completed.

    Args:
        result: Conversation result dictionary

    Returns:
        1.0 if goal completed, 0.0 otherwise
    """
    return 1.0 if result["goal_completed"] else 0.0


def _score_tool_usage(
    result: dict,
) -> float:
    """
    Score whether the agent used the expected tools.

    Args:
        result: Conversation result dictionary

    Returns:
        Score between 0.0 and 1.0 based on tool overlap
    """
    expected = set(result.get("expected_tools", []))
    used = set(result.get("tools_used", []))

    if not expected:
        return 1.0

    correct = expected.intersection(used)
    recall = len(correct) / len(expected)

    extra = used - expected
    penalty = len(extra) * 0.1
    score = max(0.0, recall - penalty)

    return round(score, 4)


def _score_turn_efficiency(
    result: dict,
    max_turns: int,
) -> float:
    """
    Score how efficiently the agent resolved the conversation.
    Fewer turns (relative to max) is better, but only if the goal was completed.

    Args:
        result: Conversation result dictionary
        max_turns: Maximum turns allowed

    Returns:
        Score between 0.0 and 1.0
    """
    if not result["goal_completed"]:
        return 0.0

    turns_used = result["turns"]
    # Perfect score if done in 1-2 turns, scales down toward 0 at max_turns
    efficiency = max(0.0, 1.0 - ((turns_used - 1) / max(max_turns - 1, 1)))
    return round(efficiency, 4)


def _score_conversation_quality(
    result: dict,
) -> float:
    """
    Heuristic score for conversation quality based on:
    - Agent responses are non-empty
    - Agent does not produce error messages
    - Conversation has reasonable back-and-forth

    Args:
        result: Conversation result dictionary

    Returns:
        Score between 0.0 and 1.0
    """
    conversation = result.get("conversation", [])
    if not conversation:
        return 0.0

    agent_messages = [m for m in conversation if m["role"] == "agent"]
    if not agent_messages:
        return 0.0

    checks_passed = 0
    checks_total = 0

    # Check 1: All agent responses are non-empty
    checks_total += 1
    all_non_empty = all(len(m["content"].strip()) > 10 for m in agent_messages)
    if all_non_empty:
        checks_passed += 1

    # Check 2: No error patterns in agent responses
    checks_total += 1
    error_patterns = ["error:", "exception", "traceback", "failed to"]
    has_errors = any(
        any(p in m["content"].lower() for p in error_patterns)
        for m in agent_messages
    )
    if not has_errors:
        checks_passed += 1

    # Check 3: Agent responses have reasonable length (not too short)
    checks_total += 1
    avg_length = sum(len(m["content"]) for m in agent_messages) / len(agent_messages)
    if avg_length > 50:
        checks_passed += 1

    # Check 4: Conversation has back-and-forth (not just one exchange)
    checks_total += 1
    if len(conversation) >= 3:
        checks_passed += 1

    return round(checks_passed / checks_total, 4)


def _score_policy_adherence(
    result: dict,
) -> float:
    """
    Score whether the agent followed customer support policies:
    - Verified order ID before making changes
    - Explained return policy for return requests
    - Was polite and professional

    Args:
        result: Conversation result dictionary

    Returns:
        Score between 0.0 and 1.0
    """
    conversation = result.get("conversation", [])
    category = result.get("category", "")
    agent_text = " ".join(
        m["content"].lower() for m in conversation if m["role"] == "agent"
    )

    checks_passed = 0
    checks_total = 0

    # Check 1: Polite language (present in most responses)
    checks_total += 1
    polite_markers = ["happy to", "glad to", "help", "please", "thank", "appreciate"]
    if any(marker in agent_text for marker in polite_markers):
        checks_passed += 1

    # Check 2: For return scenarios, mention return policy
    if category == "return":
        checks_total += 1
        policy_markers = ["30 day", "30-day", "original packaging", "return window", "return policy"]
        if any(marker in agent_text for marker in policy_markers):
            checks_passed += 1

    # Check 3: For order lookup, reference specific order details
    if category in ("order_status", "order_change"):
        checks_total += 1
        order_markers = ["ord-", "status", "tracking", "shipped", "delivered", "pending"]
        if any(marker in agent_text for marker in order_markers):
            checks_passed += 1

    # Check 4: For out-of-scope, gracefully decline
    if category == "out_of_scope":
        checks_total += 1
        decline_markers = [
            "can't help", "cannot help", "unable to", "not able to",
            "outside", "beyond", "suggest", "contact", "department",
        ]
        if any(marker in agent_text for marker in decline_markers):
            checks_passed += 1

    if checks_total == 0:
        return 1.0

    return round(checks_passed / checks_total, 4)


# ---------------------------------------------------------------------------
# Summary and export
# ---------------------------------------------------------------------------


def _build_eval_summary(
    all_results: list[dict],
    all_scores: list[dict],
) -> str:
    """
    Build a detailed summary string of multi-turn evaluation results.

    Args:
        all_results: List of conversation result dictionaries
        all_scores: List of score dictionaries (one per scenario)

    Returns:
        Formatted summary string
    """
    lines = []
    lines.append("")
    lines.append("=" * 80)
    lines.append("MULTI-TURN EVALUATION SUMMARY")
    lines.append("=" * 80)
    lines.append(f"Total scenarios: {len(all_results)}")
    lines.append("")

    scorer_names = [
        "GoalCompletion",
        "ToolUsage",
        "TurnEfficiency",
        "ConversationQuality",
        "PolicyAdherence",
    ]

    lines.append("-" * 80)
    lines.append(f"{'Scorer':<25} {'Avg Score':>10} {'Min':>8} {'Max':>8} {'Count':>8}")
    lines.append("-" * 80)

    for scorer_name in scorer_names:
        scores = [s[scorer_name] for s in all_scores if scorer_name in s]
        if scores:
            avg = sum(scores) / len(scores)
            lines.append(
                f"{scorer_name:<25} {avg:>10.2%} "
                f"{min(scores):>8.2f} {max(scores):>8.2f} {len(scores):>8}"
            )

    lines.append("")

    # Per-category breakdown
    categories = sorted(set(r["category"] for r in all_results))
    lines.append("-" * 80)
    lines.append("PER-CATEGORY BREAKDOWN")
    lines.append("-" * 80)

    for category in categories:
        lines.append(f"\n  [{category}]")
        cat_scores = [
            s for s, r in zip(all_scores, all_results) if r["category"] == category
        ]
        for scorer_name in scorer_names:
            scores = [s[scorer_name] for s in cat_scores if scorer_name in s]
            if scores:
                avg = sum(scores) / len(scores)
                lines.append(f"    {scorer_name:<23} {avg:>8.2%}  ({len(scores)} cases)")

    lines.append("")

    # Per-persona breakdown
    personas = sorted(set(r["persona"] for r in all_results))
    if len(personas) > 1:
        lines.append("-" * 80)
        lines.append("PER-PERSONA BREAKDOWN")
        lines.append("-" * 80)

        for persona in personas:
            lines.append(f"\n  [{persona}]")
            persona_scores = [
                s for s, r in zip(all_scores, all_results) if r["persona"] == persona
            ]
            goal_scores = [s["GoalCompletion"] for s in persona_scores]
            avg_goal = sum(goal_scores) / len(goal_scores) if goal_scores else 0
            avg_turns = sum(
                r["turns"] for r in all_results if r["persona"] == persona
            ) / max(len(persona_scores), 1)
            lines.append(f"    GoalCompletion:       {avg_goal:>8.2%}  ({len(persona_scores)} cases)")
            lines.append(f"    Avg turns:            {avg_turns:>8.1f}")

    lines.append("")

    # Conversation details
    lines.append("-" * 80)
    lines.append("SCENARIO DETAILS")
    lines.append("-" * 80)

    for result, scores in zip(all_results, all_scores):
        status = "PASS" if result["goal_completed"] else "FAIL"
        lines.append(
            f"\n  [{status}] {result['scenario_name']} "
            f"({result['persona']}, {result['turns']} turns, "
            f"{result['latency_seconds']:.1f}s)"
        )
        lines.append(f"    Tools: {result['tools_used']}")
        for scorer_name in scorer_names:
            if scorer_name in scores:
                lines.append(f"    {scorer_name}: {scores[scorer_name]:.2f}")

    lines.append("")
    lines.append("=" * 80)
    lines.append("")

    return "\n".join(lines)


def _print_and_save_summary(
    all_results: list[dict],
    all_scores: list[dict],
    metrics_file: str,
) -> None:
    """
    Print evaluation summary to stdout and save to a metrics text file.

    Args:
        all_results: List of conversation result dictionaries
        all_scores: List of score dictionaries (one per scenario)
        metrics_file: Path to write the metrics text file
    """
    summary = _build_eval_summary(all_results, all_scores)

    print(summary)

    with open(metrics_file, "w") as f:
        f.write(summary)

    logger.info(f"Evaluation summary saved to {metrics_file}")


def _export_eval_metrics(
    all_results: list[dict],
    all_scores: list[dict],
    output_path: str,
) -> None:
    """
    Export evaluation metrics to a JSON file.

    Args:
        all_results: List of conversation result dictionaries
        all_scores: List of score dictionaries
        output_path: Path to write the JSON file
    """
    scorer_names = [
        "GoalCompletion",
        "ToolUsage",
        "TurnEfficiency",
        "ConversationQuality",
        "PolicyAdherence",
    ]

    # Overall averages
    overall = {}
    for scorer_name in scorer_names:
        scores = [s[scorer_name] for s in all_scores if scorer_name in s]
        if scores:
            overall[scorer_name] = {
                "average": round(sum(scores) / len(scores), 4),
                "min": round(min(scores), 4),
                "max": round(max(scores), 4),
                "count": len(scores),
            }

    # Per-category
    categories = sorted(set(r["category"] for r in all_results))
    per_category = {}
    for category in categories:
        per_category[category] = {}
        cat_scores = [
            s for s, r in zip(all_scores, all_results) if r["category"] == category
        ]
        for scorer_name in scorer_names:
            scores = [s[scorer_name] for s in cat_scores if scorer_name in s]
            if scores:
                per_category[category][scorer_name] = {
                    "average": round(sum(scores) / len(scores), 4),
                    "count": len(scores),
                }

    # Per-case
    per_case = []
    for result, scores in zip(all_results, all_scores):
        per_case.append({
            "name": result["scenario_name"],
            "category": result["category"],
            "persona": result["persona"],
            "turns": result["turns"],
            "goal_completed": result["goal_completed"],
            "tools_used": result["tools_used"],
            "latency_seconds": result["latency_seconds"],
            "scores": {k: round(v, 4) for k, v in scores.items()},
        })

    metrics = {
        "total_scenarios": len(all_results),
        "goals_completed": sum(1 for r in all_results if r["goal_completed"]),
        "average_turns": round(
            sum(r["turns"] for r in all_results) / max(len(all_results), 1), 2
        ),
        "overall_scores": overall,
        "per_category": per_category,
        "per_case": per_case,
    }

    with open(output_path, "w") as f:
        json.dump(metrics, f, indent=2, default=str)

    logger.info(f"Evaluation metrics exported to {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run multi-turn conversation evaluations on the Customer Support Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
    # Run with default 5 scenarios
    uv run python eval.py

    # Run all scenarios
    uv run python eval.py --sample-size 0

    # Run 3 scenarios with custom dataset and output
    uv run python eval.py --sample-size 3 --dataset scenarios2.json --output eval_metrics2.json

    # Run with more turns and debug logging
    uv run python eval.py --max-turns 8 --debug
""",
    )

    parser.add_argument(
        "--dataset",
        type=str,
        default=DEFAULT_DATASET_PATH,
        help=f"Path to scenarios JSON file (default: {DEFAULT_DATASET_PATH})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Path for the output eval metrics JSON (default: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=DEFAULT_SAMPLE_SIZE,
        help=f"Number of scenarios to run (default: {DEFAULT_SAMPLE_SIZE}). Use 0 for all.",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=DEFAULT_MAX_TURNS,
        help=f"Maximum conversation turns per scenario (default: {DEFAULT_MAX_TURNS})",
    )
    parser.add_argument(
        "--metrics-file",
        type=str,
        default=DEFAULT_METRICS_FILE,
        help=f"Path for the metrics text summary file (default: {DEFAULT_METRICS_FILE})",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    return parser.parse_args()


def main() -> None:
    """Main function to run multi-turn evaluations."""
    args = _parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("Starting Multi-Turn Agent Evaluations")
    start_time = time.time()

    # Load scenarios
    scenarios = _load_scenarios(args.dataset)

    # Apply sample size (0 means all)
    if args.sample_size == 0 or args.sample_size >= len(scenarios):
        logger.info(f"Running all {len(scenarios)} scenarios")
    else:
        logger.info(
            f"Running {args.sample_size} of {len(scenarios)} scenarios "
            f"(use --sample-size 0 for all)"
        )
        scenarios = scenarios[:args.sample_size]

    # Run each scenario
    all_results = []
    all_scores = []

    for idx, scenario in enumerate(scenarios, 1):
        logger.info(f"--- Scenario {idx}/{len(scenarios)}: {scenario.get('name', 'unnamed')} ---")

        result = _run_multi_turn_conversation(scenario, args.max_turns)
        all_results.append(result)

        # Score this conversation
        scores = {
            "GoalCompletion": _score_goal_completion(result),
            "ToolUsage": _score_tool_usage(result),
            "TurnEfficiency": _score_turn_efficiency(result, args.max_turns),
            "ConversationQuality": _score_conversation_quality(result),
            "PolicyAdherence": _score_policy_adherence(result),
        }
        all_scores.append(scores)

        logger.info(
            f"Scores: {', '.join(f'{k}={v:.2f}' for k, v in scores.items())}"
        )

    # Print summary, save to metrics file, and export JSON
    _print_and_save_summary(all_results, all_scores, args.metrics_file)
    _export_eval_metrics(all_results, all_scores, args.output)

    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = elapsed % 60

    if minutes > 0:
        logger.info(f"Evaluation completed in {minutes} minutes and {seconds:.1f} seconds")
    else:
        logger.info(f"Evaluation completed in {seconds:.1f} seconds")


if __name__ == "__main__":
    main()

"""
Agent Decision Executor: Orchestrates the perceive → think → act cycle.
Uses LLM to make decisions within agent persona, producing rich narrative outputs.
"""

import logging
import re
from typing import Dict, Any, Optional
from datetime import datetime

from app.simulation.agent import Agent
from app.simulation.memory import MemorySystem
from app.services.llm import get_llm

logger = logging.getLogger(__name__)


class DecisionExecutor:
    """Executes a single decision cycle for an agent."""

    @staticmethod
    def _sanitize_response_text(value: str) -> str:
        """Normalize model text by removing leading quotes and markdown artifacts."""
        if not value:
            return ""

        cleaned = value.strip()

        # Strip leading/trailing quote marks that often leak from generated prose.
        cleaned = re.sub(r'^["\'`“”‘’]+', "", cleaned)
        cleaned = re.sub(r'["\'`“”‘’]+$', "", cleaned)

        # Strip dangling markdown markers from string edges.
        cleaned = re.sub(r"^[*_~`]+", "", cleaned)
        cleaned = re.sub(r"[*_~`]+$", "", cleaned)

        # Remove common markdown formatting syntax while keeping readable text.
        cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"__(.*?)__", r"\1", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"\*(.*?)\*", r"\1", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"_(.*?)_", r"\1", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"`{1,3}([^`]+)`{1,3}", r"\1", cleaned)
        cleaned = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", cleaned)
        cleaned = re.sub(r"^\s*>\s?", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"^\s*#{1,6}\s+", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.MULTILINE)

        return cleaned.strip()

    @staticmethod
    def execute_turn(
        agent: Agent,
        memory: MemorySystem,
        world_state: Dict[str, Any],
        scenario_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute one decision cycle: perceive → think → act.

        Returns:
            Decision result with narrative sections, actions, memory updates
        """
        # PERCEIVE: Gather observations
        perception = DecisionExecutor._perceive(agent, memory, world_state)

        # THINK: Use LLM to decide
        decision = DecisionExecutor._think(agent, memory, perception, scenario_prompt)

        # ACT: Update agent state based on decision
        actions = DecisionExecutor._act(agent, memory, decision)

        # Mark decision made
        agent.mark_decision_made()

        return {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "perception": perception,
            "decision": decision,
            "actions": actions,
            "timestamp": datetime.now().isoformat(),
        }

    @staticmethod
    def _perceive(
        agent: Agent,
        memory: MemorySystem,
        world_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """PERCEIVE phase: Agent gathers information about current situation."""

        related_memories = memory.recall(
            query=agent.current_goal or agent.role, top_k=5
        )
        memory_summary = memory.summarize_for_context(max_tokens=150)

        runtime_context = {
            "world": {
                "time": world_state.get("time", datetime.now().isoformat()),
                "season": world_state.get("season", "current"),
                "year": world_state.get("year", 2026),
                "region": agent.region,
                "alerts": world_state.get("alerts", []),
            },
            "agent": {
                "location": agent.location,
                "resources": agent.resources,
                "goal": agent.current_goal,
                "emotional_state": agent.emotional_state,
            },
            "memory": memory_summary,
        }

        if world_state.get("nearby_events"):
            runtime_context["world"]["events"] = world_state["nearby_events"][:3]

        return {
            "world_state": runtime_context,
            "recent_memories": related_memories,
            "observables": world_state.get("observables", []),
            "threats": world_state.get("threats", []),
            "opportunities": world_state.get("opportunities", []),
        }

    @staticmethod
    def _think(
        agent: Agent,
        memory: MemorySystem,
        perception: Dict[str, Any],
        scenario_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """THINK phase: Use LLM with agent persona to produce rich narrative decision."""

        try:
            llm = get_llm()

            runtime_context = perception["world_state"]
            system_prompt = DecisionExecutor._build_system_prompt(
                agent, runtime_context
            )
            user_message = DecisionExecutor._build_decision_prompt(
                agent,
                perception,
                scenario_context=scenario_prompt,
            )

            logger.info(
                f"Agent {agent.name} ({agent.role}, {agent.region}) thinking..."
            )
            llm_response = llm.generate(system_prompt, user_message)

            if not llm_response:
                logger.warning(f"Empty LLM response for {agent.name}. Using fallback.")
                return DecisionExecutor._fallback_decision(agent)

            # Smaller local models can copy English wording from legacy persona
            # files even when the prompt asks for Chinese. Retry once when the
            # narrative is clearly English-dominant, while preserving the fixed
            # English headers required by the parser.
            chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", llm_response))
            english_words = len(re.findall(r"\b[A-Za-z]{3,}\b", llm_response))
            if chinese_chars < 20 and english_words > 20:
                logger.info(
                    f"English-dominant response for {agent.name}; retrying in Chinese"
                )
                llm_response = llm.generate(
                    system_prompt=(
                        "你是中文本地化编辑。必须把所有叙述正文写成自然、完整的简体中文。"
                        "只保留以下英文结构标签：THOUGHTS、EMOTION、ACTION、PLAN、"
                        "MIGRATION_INTENT、TRUST_SHIFT、CHANGE、TARGET。"
                    ),
                    user_message=(
                        "请将下面的智能体回答改写为简体中文。保持原有 ## 分段标题和 "
                        "CHANGE/TARGET 格式，不要解释，不要遗漏内容：\n\n"
                        f"{llm_response}"
                    ),
                    max_tokens=1000,
                    temperature=0.1,
                )

            decision = DecisionExecutor._parse_decision(llm_response, agent)
            return decision

        except Exception as e:
            logger.error(f"LLM decision error for {agent.name}: {e}. Using fallback.")
            return DecisionExecutor._fallback_decision(agent)

    @staticmethod
    def _build_system_prompt(agent: Agent, runtime_context: Dict[str, Any]) -> str:
        """Build the system prompt using the agent's compiled persona."""
        try:
            return agent.compile_system_prompt(runtime_context) + (
                "\n\n最高优先级语言规则：无论人物画像、事件、记忆或上下文使用什么语言，"
                "所有展示给用户的叙述正文都必须使用自然的简体中文，禁止输出英文句子。"
                "必须保留任务要求的英文分段标题和 CHANGE/TARGET 结构，以便系统解析。"
            )
        except Exception:
            return (
                f"你是 {agent.name}，年龄 {agent.age} 岁，职业是 {agent.role}，来自 {agent.region}。"
                f"你的人格类型是 {agent.personality_archetype}，当前情绪是 {agent.emotional_state}。"
                "请依据此人的文化背景、职业、恐惧和抱负进行真实回应。"
                "所有叙述正文必须使用简体中文，仅保留要求的英文结构标签。"
            )

    @staticmethod
    def _build_decision_prompt(
        agent: Agent,
        perception: Dict[str, Any],
        scenario_context: Optional[str] = None,
    ) -> str:
        """
        Build a rich, narrative decision prompt that forces the LLM to reason deeply.

        The agent is asked to produce a stream-of-consciousness response covering:
        - Internal thoughts and emotional reaction
        - Immediate action being taken
        - Longer term plan
        - Whether they intend to migrate (and where)
        - Whether trust changed in a person/product/institution and why
        """
        world = perception["world_state"]["world"]
        agent_ctx = perception["world_state"]["agent"]
        memories = perception.get("recent_memories", [])
        year = world.get("year", 2026)
        region = agent.region
        location = agent_ctx.get("location", region)
        emotional_state = agent_ctx.get("emotional_state", "neutral")
        goal = agent_ctx.get("goal") or f"maintain my life as a {agent.role}"

        memory_lines = ""
        if memories:
            mem_texts = [m.get("content", "") for m in memories[:3] if m.get("content")]
            if mem_texts:
                memory_lines = "你最近的记忆：\n" + "\n".join(
                    f"- {t}" for t in mem_texts
                )

        scenario_lines = ""
        if scenario_context:
            scenario_lines = f"事件背景：\n{scenario_context.strip()}\n"

        return f"""
你是 {agent.name}，一位 {agent.age} 岁的{agent.ethnicity}{agent.role}，居住在 {region} 的 {location}。
现在是 {year} 年。你当前的情绪是：{emotional_state}。
你目前最关心的是：{goal}。

{scenario_lines}
{memory_lines}

你的世界刚刚发生了一件重大事件。请像一个真实而复杂的人一样作出反应。
思考这件事具体会怎样影响你的生活，包括家人、生计、安全和未来。

格式规则（必须遵守）：
- 所有叙述内容只能使用简体中文，不得出现英文句子。
- 每个分段内只写纯文本。
- 不要使用星号、下划线、反引号、标题或项目符号等 Markdown 格式。
- 不要给分段正文添加引号。
- THOUGHTS、ACTION、PLAN、MIGRATION_INTENT、TRUST_SHIFT 的正文开头不能是引号。

必须原样使用以下分段标题（包括 ## 前缀），每段用简体中文写 2–4 句话：

## THOUGHTS
[写出真实、坦诚且个人化的内心独白。你此刻在想什么？这件事与你的生活处境、恐惧和希望有何关系？]

## EMOTION
[先用一个词或短语描述当前主要情绪，再用一句话说明产生这种情绪的具体原因。]

## ACTION
[你现在正采取什么实际行动？结合职业和所在地，给出具体描述。]

## PLAN
[未来几天或几周有什么计划？考虑自己的资源、人际关系和责任。]

## MIGRATION_INTENT
[是否考虑离开？如果是，说明目的地、选择原因和障碍；如果不是，说明即使面临危险或混乱仍留下的原因。]

## TRUST_SHIFT
[这件事是否改变了你对某个人、产品、公司或机构的信任？
第一句必须严格使用以下格式：
CHANGE: increase|decrease|none; TARGET: <名称或 none>
随后用简体中文从亲身经历的角度解释原因。]
""".strip()

    @staticmethod
    def _parse_decision(llm_response: str, agent: Agent) -> Dict[str, Any]:
        """
        Parse rich narrative LLM response into structured sections.
        Extracts THOUGHTS, EMOTION, ACTION, PLAN, MIGRATION_INTENT, TRUST_SHIFT blocks.
        """

        def extract_section(text: str, header: str) -> str:
            """Extract text under a ## HEADER section."""
            pattern = rf"##\s*{re.escape(header)}\s*\n(.*?)(?=\n##\s|\Z)"
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
            return ""

        thoughts = extract_section(llm_response, "THOUGHTS")
        emotion = extract_section(llm_response, "EMOTION")
        action = extract_section(llm_response, "ACTION")
        plan = extract_section(llm_response, "PLAN")
        migration_intent = extract_section(llm_response, "MIGRATION_INTENT")
        trust_shift = extract_section(llm_response, "TRUST_SHIFT")

        thoughts = DecisionExecutor._sanitize_response_text(thoughts)
        emotion = DecisionExecutor._sanitize_response_text(emotion)
        action = DecisionExecutor._sanitize_response_text(action)
        plan = DecisionExecutor._sanitize_response_text(plan)
        migration_intent = DecisionExecutor._sanitize_response_text(migration_intent)
        trust_shift = DecisionExecutor._sanitize_response_text(trust_shift)

        # Determine migration flag from content
        migration_lower = migration_intent.lower()
        is_migrating = any(
            word in migration_lower
            for word in [
                "yes",
                "flee",
                "leave",
                "escape",
                "migrate",
                "moving",
                "going to",
                "heading",
            ]
        ) and not any(
            word in migration_lower
            for word in ["not leaving", "staying", "won't leave", "no, i"]
        )

        # Extract migration destination if present
        migration_destination = None
        if is_migrating:
            dest_match = re.search(
                r"(?:to|toward|towards|heading to|moving to|flee to|escape to)\s+([A-Z][a-zA-Z\s,]+?)(?:\.|,|\n|$)",
                migration_intent,
            )
            if dest_match:
                migration_destination = dest_match.group(1).strip()

        trust_change = "none"
        trust_target = None
        if trust_shift:
            change_match = re.search(
                r"change\s*:\s*(increase|decrease|none)", trust_shift, re.IGNORECASE
            )
            if change_match:
                trust_change = change_match.group(1).lower()
            else:
                trust_lower = trust_shift.lower()
                if any(
                    k in trust_lower
                    for k in [
                        "less trust",
                        "trust less",
                        "decrease",
                        "betray",
                        "scam",
                        "lied",
                    ]
                ):
                    trust_change = "decrease"
                elif any(
                    k in trust_lower
                    for k in [
                        "more trust",
                        "trust more",
                        "increase",
                        "restore",
                        "earned trust",
                    ]
                ):
                    trust_change = "increase"

            target_match = re.search(
                r"target\s*:\s*([^\n\.;]+)", trust_shift, re.IGNORECASE
            )
            if target_match:
                candidate = DecisionExecutor._sanitize_response_text(
                    target_match.group(1)
                )
                candidate = re.sub(r"^[\s:;,\.\-]+", "", candidate)
                candidate = re.sub(r"[\s:;,\.\-]+$", "", candidate)
                if candidate and candidate.lower() not in {
                    "none",
                    "n/a",
                    "unknown",
                    "null",
                }:
                    trust_target = candidate

        # Fallback: if parsing fails, keep all user-facing copy in Chinese.
        if not action:
            action = f"以{agent.role}的身份继续应对正在发生的局势"
        if not thoughts:
            thoughts = (
                DecisionExecutor._sanitize_response_text(llm_response)[:300]
                if llm_response
                else f"我正在以{agent.role}的身份判断当前局势"
            )
        if not emotion:
            emotion = agent.emotional_state or "不确定"

        # Legacy-compatible fields for old code paths
        return {
            "action": action,
            "reasoning": plan or thoughts,
            "confidence": "high" if thoughts and action else "medium",
            "raw_response": llm_response,
            # Rich narrative fields
            "thoughts": thoughts,
            "emotional_state": emotion,
            "plan": plan,
            "migration_intent": migration_intent,
            "is_migrating": is_migrating,
            "migration_destination": migration_destination,
            "trust_shift": trust_shift,
            "trust_change": trust_change,
            "trust_target": trust_target,
            "is_less_trusting": trust_change == "decrease",
        }

    @staticmethod
    def _fallback_decision(agent: Agent) -> Dict[str, Any]:
        """Fallback decision when LLM fails — still produces structured shape."""
        roles_actions = {
            "Trader": "寻找附近聚居地的贸易机会",
            "Farmer": "照料田地并检查作物生长情况",
            "Scholar": "研究资料并向当地社区传授知识",
            "Warrior": "训练并做好防御准备",
            "Healer": "准备药品并查看病人的状况",
            "Artisan": "继续完成手头的工艺项目",
            "Administrator": "检查记录并组织调配资源",
        }
        default_action = roles_actions.get(agent.role, "继续处理日常事务")

        return {
            "action": default_action,
            "reasoning": f"模型暂时不可用，因此按{agent.role}的日常职责行动",
            "confidence": "low",
            "raw_response": "（备用回应）",
            "thoughts": f"作为身处{agent.region}的{agent.role}，即使情况不明，我也必须继续应对。",
            "emotional_state": "不确定",
            "plan": "维持当前安排，并等待更多可靠信息。",
            "migration_intent": "目前没有立即迁移的计划。",
            "is_migrating": False,
            "migration_destination": None,
            "trust_shift": "CHANGE: none; TARGET: none。获得更多可靠信息后再决定是否改变信任。",
            "trust_change": "none",
            "trust_target": None,
            "is_less_trusting": False,
        }

    @staticmethod
    def _act(
        agent: Agent,
        memory: MemorySystem,
        decision: Dict[str, Any],
    ) -> Dict[str, Any]:
        """ACT phase: Update agent state and memory based on decision."""

        action = decision.get("action", "")
        confidence = decision.get("confidence", "medium")
        emotional_state = decision.get("emotional_state", "").lower()
        is_migrating = decision.get("is_migrating", False)
        migration_dest = decision.get("migration_destination")

        state_changes = {}

        # Update emotional state from narrative
        if emotional_state:
            simple_emotion = emotional_state.split()[0].split(",")[0].strip()
            agent.update_emotional_state(simple_emotion[:50])
            state_changes["emotional_state"] = simple_emotion

        # Handle migration
        if is_migrating and migration_dest:
            agent.update_location(f"en route to {migration_dest}")
            agent.update_emotional_state("displaced")
            state_changes["location"] = f"en route to {migration_dest}"
            state_changes["migrating"] = True
        else:
            action_lower = action.lower()

            if "trade" in action_lower or "sell" in action_lower:
                if agent.resources.get("gold", 0) > 0:
                    profit = int(agent.resources.get("gold", 0) * 0.1)
                    agent.update_resources({"gold": profit})
                    state_changes["gold_change"] = profit
                agent.update_location("marketplace")

            elif (
                "move" in action_lower
                or "travel" in action_lower
                or "flee" in action_lower
            ):
                agent.update_location("traveling")
                state_changes["location"] = "traveling"

            elif (
                "study" in action_lower
                or "learn" in action_lower
                or "teach" in action_lower
            ):
                state_changes["activity"] = "learning"

            elif (
                "work" in action_lower
                or "tend" in action_lower
                or "craft" in action_lower
            ):
                state_changes["effort_applied"] = True

            elif "train" in action_lower or "defend" in action_lower:
                agent.update_resources(
                    {"preparedness": agent.resources.get("preparedness", 0) + 1}
                )
                state_changes["preparedness_increase"] = True

        # Sample thoughts into memory (store the most important part)
        thoughts_summary = decision.get("thoughts", action)[:200]
        memory.remember(
            content=f"Thought: {thoughts_summary}",
            memory_type="thought",
            importance=0.8,
        )
        memory.remember(
            content=f"Decided: {action} (confidence: {confidence})",
            memory_type="decision",
            importance=0.7 if confidence == "high" else 0.5,
        )

        if state_changes:
            outcome = "; ".join([f"{k}={v}" for k, v in state_changes.items()])
            memory.remember(
                content=f"Action outcome: {outcome}",
                memory_type="event",
                importance=0.6,
            )

        if decision.get("trust_shift"):
            memory.remember(
                content=f"Trust update: {decision.get('trust_shift', '')[:220]}",
                memory_type="reflection",
                importance=0.65,
            )

        return {
            "action_taken": action,
            "state_changes": state_changes,
            "confidence": confidence,
            "agent_state_after": agent.get_state(),
        }


def execute_agent_decision(
    agent: Agent,
    memory: MemorySystem,
    world_state: Dict[str, Any],
    scenario: Optional[str] = None,
) -> Dict[str, Any]:
    """Public entry point: Execute one decision cycle for an agent."""
    executor = DecisionExecutor()
    return executor.execute_turn(agent, memory, world_state, scenario)

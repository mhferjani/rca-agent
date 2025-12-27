"""LLM-based log analyzer for root cause analysis - Multi-model support."""

import uuid
from datetime import datetime
from typing import Any

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from rca_agent.analyzers.pattern_matcher import PatternMatcher
from rca_agent.models.context import RCAContext
from rca_agent.models.reports import (
    ErrorCategory,
    RCAReport,
    Recommendation,
    Severity,
    SimilarIncident,
)

logger = structlog.get_logger()


class LLMAnalysisResult(BaseModel):
    """Structured output from LLM analysis."""

    error_category: ErrorCategory
    severity: Severity
    root_cause: str = Field(description="Detailed root cause explanation")
    root_cause_summary: str = Field(description="One-line summary")
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    contributing_factors: list[str] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    immediate_action: str | None = None


SYSTEM_PROMPT = """You are an expert Data Engineering incident responder. Your job is to analyze pipeline failures and identify root causes quickly and accurately.

You will be given:
1. Task metadata and logs from a failed pipeline
2. Historical context (past runs, recent changes)
3. Source health status
4. Pattern matching results from known error signatures

Your analysis should:
- Identify the most likely root cause
- Assess confidence level based on available evidence
- Provide actionable recommendations
- Consider whether this might be related to recent changes

Be concise but thorough. Focus on actionable insights.

{format_instructions}
"""

ANALYSIS_PROMPT = """Analyze this pipeline failure and provide a structured diagnosis.

{context}

## Pattern Matching Results
{pattern_results}

## Similar Past Incidents
{similar_incidents}

Based on all available evidence, provide your root cause analysis.
"""


def create_llm(
    provider: str,
    model: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.1,
    **kwargs: Any,
) -> tuple[BaseChatModel, str]:
    """Factory function to create LLM based on provider.

    Args:
        provider: LLM provider ("anthropic", "openai", "huggingface", "ollama")
        model: Model name (uses provider default if not specified)
        api_key: API key (uses env var if not provided)
        temperature: Sampling temperature
        **kwargs: Additional provider-specific arguments

    Returns:
        Tuple of (LLM instance, model_name)
    """

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        model_name = model or "claude-sonnet-4-20250514"
        llm = ChatAnthropic(
            model=model_name,
            api_key=api_key,
            temperature=temperature,
            max_tokens=4096,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        model_name = model or "gpt-4o"
        llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            temperature=temperature,
        )

    elif provider == "huggingface":
        from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

        model_name = model or "mistralai/Mixtral-8x7B-Instruct-v0.1"

        # HuggingFace Inference API
        endpoint = HuggingFaceEndpoint(
            repo_id=model_name,
            huggingfacehub_api_token=api_key,
            temperature=temperature,
            max_new_tokens=4096,
            **kwargs,
        )
        llm = ChatHuggingFace(llm=endpoint)

    elif provider == "huggingface_local":
        import torch
        from langchain_huggingface import ChatHuggingFace, HuggingFacePipeline

        model_name = model or "mistralai/Mistral-7B-Instruct-v0.2"

        # Local HuggingFace model
        llm = HuggingFacePipeline.from_model_id(
            model_id=model_name,
            task="text-generation",
            device=0 if torch.cuda.is_available() else -1,
            pipeline_kwargs={
                "temperature": temperature,
                "max_new_tokens": 4096,
                "do_sample": True,
            },
        )
        llm = ChatHuggingFace(llm=llm)

    elif provider == "mistral":
        from langchain_mistralai import ChatMistralAI

        model_name = model or "open-mistral-7b"
        llm = ChatMistralAI(
            model=model_name,
            api_key=api_key,
            temperature=temperature,
            max_tokens=4096,
        )
    elif provider == "ollama":
        from langchain_ollama import ChatOllama

        model_name = model or "mistral"
        llm = ChatOllama(
            model=model_name,
            temperature=temperature,
            base_url=kwargs.get("base_url", "http://localhost:11434"),
        )

    else:
        raise ValueError(
            f"Unknown provider: {provider}. "
            f"Supported: anthropic, openai, huggingface, huggingface_local, ollama"
        )

    return llm, model_name


class LLMAnalyzer:
    """LLM-based analyzer for root cause diagnosis.

    Supports multiple LLM providers:
    - anthropic: Claude (API)
    - openai: GPT-4 (API)
    - huggingface: HuggingFace Inference API
    - huggingface_local: Local HuggingFace models
    - ollama: Local Ollama models

    Example:
        # Anthropic (default)
        analyzer = LLMAnalyzer(provider="anthropic")

        # OpenAI
        analyzer = LLMAnalyzer(provider="openai", model="gpt-4o")

        # HuggingFace API
        analyzer = LLMAnalyzer(
            provider="huggingface",
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            api_key="hf_xxx"
        )

        # Ollama (local)
        analyzer = LLMAnalyzer(provider="ollama", model="mistral")
    """

    def __init__(
        self,
        provider: str = "anthropic",
        model: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> None:
        """Initialize LLM analyzer.

        Args:
            provider: LLM provider ("anthropic", "openai", "huggingface", "huggingface_local", "ollama")
            model: Model name (defaults to provider's best model)
            api_key: API key (uses env var if not provided)
            temperature: Sampling temperature
            **kwargs: Additional provider-specific arguments
        """
        self.provider = provider
        self.temperature = temperature
        self.logger = logger.bind(component="llm_analyzer")

        self.llm, self.model_name = create_llm(
            provider=provider,
            model=model,
            api_key=api_key,
            temperature=temperature,
            **kwargs,
        )

        self.pattern_matcher = PatternMatcher()
        self.output_parser = PydanticOutputParser(pydantic_object=LLMAnalysisResult)

        self.logger.info(
            "Initialized LLM analyzer",
            provider=provider,
            model=self.model_name,
        )

    def _format_pattern_results(
        self,
        context: RCAContext,
    ) -> str:
        """Format pattern matching results for prompt."""
        log_content = context.logs.stdout
        matches = self.pattern_matcher.match(log_content)

        if not matches:
            return "No known error patterns detected."

        lines = []
        for pattern, matched_strings in matches[:5]:
            lines.append(
                f"- **{pattern.name}** ({pattern.category.value}, {pattern.severity.value}): "
                f"{pattern.description}"
            )
            lines.append(f"  Matches: {', '.join(matched_strings[:3])}")
            lines.append(f"  Recommendation: {pattern.recommendation}")

        return "\n".join(lines)

    def _format_similar_incidents(
        self,
        similar_incidents: list[SimilarIncident],
    ) -> str:
        """Format similar incidents for prompt."""
        if not similar_incidents:
            return "No similar past incidents found."

        lines = []
        for incident in similar_incidents[:3]:
            lines.append(
                f"- [{incident.date.strftime('%Y-%m-%d')}] {incident.dag_id}/{incident.task_id}: "
                f"{incident.root_cause}"
            )
            if incident.resolution:
                lines.append(f"  Resolution: {incident.resolution}")

        return "\n".join(lines)

    async def analyze(
        self,
        context: RCAContext,
        similar_incidents: list[SimilarIncident] | None = None,
    ) -> RCAReport:
        """Analyze failure context and generate RCA report.

        Args:
            context: Aggregated context from collectors
            similar_incidents: Similar past incidents from knowledge base

        Returns:
            Complete RCA report
        """
        start_time = datetime.utcnow()
        self.logger.info(
            "Starting LLM analysis",
            dag_id=context.task.dag_id,
            task_id=context.task.task_id,
            provider=self.provider,
            model=self.model_name,
        )

        similar_incidents = similar_incidents or []

        # Build prompt
        format_instructions = self.output_parser.get_format_instructions()
        system_message = SystemMessage(
            content=SYSTEM_PROMPT.format(format_instructions=format_instructions)
        )

        human_message = HumanMessage(
            content=ANALYSIS_PROMPT.format(
                context=context.to_prompt_context(),
                pattern_results=self._format_pattern_results(context),
                similar_incidents=self._format_similar_incidents(similar_incidents),
            )
        )

        # Invoke LLM
        try:
            response = await self.llm.ainvoke([system_message, human_message])
            result = self.output_parser.parse(response.content)
        except Exception as e:
            self.logger.exception("LLM analysis failed", error=str(e))
            # Fallback to pattern-based analysis
            result = self._fallback_analysis(context)

        # Calculate analysis duration
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        # Extract key log lines
        key_lines = self.pattern_matcher.extract_key_lines(context.logs.stdout)

        # Build recommendations
        recommendations = [
            Recommendation(
                action=r.get("action", ""),
                priority=r.get("priority", 3),
                estimated_effort=r.get("estimated_effort"),
                automated=r.get("automated", False),
            )
            for r in result.recommendations
        ]

        # Determine collectors used
        collectors_used = ["airflow"]
        if context.git:
            collectors_used.append("git")
        if context.sources:
            collectors_used.append("source_health")
        if context.metrics:
            collectors_used.append("metrics")

        # Build report
        report = RCAReport(
            report_id=str(uuid.uuid4()),
            dag_id=context.task.dag_id,
            task_id=context.task.task_id,
            run_id=context.task.run_id,
            failure_time=context.failure_time,
            error_category=result.error_category,
            severity=result.severity,
            root_cause=result.root_cause,
            root_cause_summary=result.root_cause_summary,
            confidence=result.confidence,
            evidence=result.evidence,
            key_log_lines=key_lines,
            contributing_factors=result.contributing_factors,
            recent_changes=[
                f"{c.short_sha}: {c.message}"
                for c in (context.git.recent_commits[:3] if context.git else [])
            ],
            recommendations=recommendations,
            immediate_action=result.immediate_action,
            similar_incidents=similar_incidents,
            is_recurring=len(similar_incidents) > 0,
            recurrence_count=len(similar_incidents),
            analysis_duration_ms=duration_ms,
            llm_model=f"{self.provider}/{self.model_name}",
            collectors_used=collectors_used,
        )

        self.logger.info(
            "Analysis complete",
            category=result.error_category.value,
            confidence=result.confidence,
            duration_ms=duration_ms,
        )

        return report

    def _fallback_analysis(self, context: RCAContext) -> LLMAnalysisResult:
        """Fallback to pattern-based analysis when LLM fails."""
        self.logger.warning("Using fallback pattern-based analysis")

        primary = self.pattern_matcher.get_primary_error(context.logs.stdout)

        if primary:
            pattern, matches = primary
            return LLMAnalysisResult(
                error_category=pattern.category,
                severity=pattern.severity,
                root_cause=pattern.description,
                root_cause_summary=pattern.description,
                confidence=0.6,
                evidence=[f"Pattern match: {m}" for m in matches[:3]],
                recommendations=[
                    {
                        "action": pattern.recommendation,
                        "priority": 1,
                        "automated": False,
                    }
                ],
            )

        # No patterns matched - return unknown
        return LLMAnalysisResult(
            error_category=ErrorCategory.UNKNOWN,
            severity=Severity.MEDIUM,
            root_cause="Unable to determine root cause from available information",
            root_cause_summary="Unknown error - manual investigation required",
            confidence=0.2,
            evidence=[],
            recommendations=[
                {
                    "action": "Review full logs manually",
                    "priority": 1,
                    "automated": False,
                }
            ],
        )

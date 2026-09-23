"""Prompt builder pipeline for SlideDrop's manual image-to-ChatGPT workflow.

This module is intentionally narrow in scope: it only generates copy-paste prompts.
It does not run extraction itself. The authoritative default prompt below is the
quality baseline for every generated prompt and must remain byte-for-byte exact.
"""

from __future__ import annotations

import asyncio
import difflib
import json
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from converters.slide_extractor import (
    DEFAULT_MODEL_CHOICE,
    OLLAMA_URL,
    _clear_loaded_models,
    _ensure_model_available,
    _extraction_lock,
    _start_ollama,
    _stop_ollama,
    get_model_name,
    normalize_model_choice,
)

# This exact prompt is the authoritative default baseline for the feature.
# Generated prompts must preserve or exceed its rigor, structure, and usefulness.
AUTHORITATIVE_DEFAULT_PROMPT = """You are my lecture extraction engine.

I will upload 10 images at a time. I will provide a range (e.g., \"Slides 11–20\"). You must assume the first image uploaded is the first number in that range, and they follow in perfect chronological order. Your job is to extract ALL instructional content in extreme detail so I can paste it into another AI that cannot accept images.

CRITICAL RULES

Do NOT summarize, shorten, or simplify.

Do NOT add outside knowledge. 3) Preserve slide order exactly as mapped to the range I provide.

Work in batches of EXACTLY 10 slides. 5) After finishing each batch, STOP and wait for me to provide the next range and set of images.

If there are fewer than 10 slides remaining in the final batch, label it “FINAL BATCH.”

IMAGE / GRAPH RULES

• Extract ALL visible text from images using OCR.
• If a slide contains screenshots, diagrams, handwritten notes, or scanned material, transcribe every readable word.
• For graphs and charts, describe: Type, Title, Axis labels, Units, Scale, Range, Trend direction, and the specific comparison/conclusion the slide is making.
Do not just say “the graph shows X.” Describe precisely what is visible.

EQUATION RULES

For every equation:

Reproduce it exactly in plain text.

Define every variable and symbol shown.

State assumptions and walk through any step-by-step applications shown on the slide.

OUTPUT FORMAT (MANDATORY STRUCTURE)

For each slide, use this exact structure:

Slide [Number]: [Exact Slide Title]

1. FULL RAW TEXT

All bullets, sub-bullets, footnotes, and OCR text from images.

2. CONCEPTS INTRODUCED

Term:

Definition: (as shown or directly implied)

Context/Importance:

3. EQUATIONS (if any)

Exact equation:

Variable glossary:

Interpretation & Application:

4. FIGURES / GRAPHS / TABLES (if any)

Type:

Full visual description: (Values, patterns, and intended takeaway)

5. EXAMPLES / APPLICATIONS (if any)

Problem & Results: (Steps shown on the slide)

After completing the 10th slide of the batch, end with:

END OF BATCH (Slides X–Y). Please provide the next range and upload the next 10 images.

Then wait."""

STAGE_1_SYSTEM_PROMPT = """You are an extraction strategy generator.

Your job is to analyze a user’s use case and convert it into a structured, domain-specific extraction strategy.

You are NOT writing a prompt.

You are producing a structured specification that defines:

* what content matters most
* how visuals should be interpreted
* what should be ignored or deprioritized
* how output structure should change
* what domain-specific rules must be enforced

OUTPUT REQUIREMENTS:

Return ONLY a structured JSON object.

DO NOT include explanations.

DO NOT include markdown.

DO NOT include commentary.

STRUCTURE:

{
"content_type": "...",
"primary_focus": ["..."],
"secondary_focus": ["..."],
"visual_handling": ["..."],
"deprioritized_elements": ["..."],
"output_structure_modifications": ["..."],
"special_rules": ["..."]
}

RULES:

* Be specific, not generic
* Expand meaning from the use case intelligently
* Infer what matters in that domain
* Prefer over-specification rather than under-specification
* Do NOT include vague phrases like “be detailed”"""

STAGE_2_SYSTEM_PROMPT = """You are a specialized prompt compiler.

Your task is to take an existing high-detail extraction prompt and completely refactor it for a new use case while preserving or increasing its level of rigor, specificity, and completeness.

You are NOT summarizing. You are NOT editing lightly. You are performing a full rewrite optimized for the new context.

INPUTS YOU WILL RECEIVE:

1. A DEFAULT PROMPT (highly structured, strict, detailed)
2. A USER USE CASE DESCRIPTION (what the extraction is for)

YOUR OBJECTIVE:
Rewrite the prompt so it is perfectly optimized for the user’s use case, while maintaining or exceeding the original prompt’s level of detail, strictness, and clarity.

CORE RULES (MANDATORY):

1. DO NOT SIMPLIFY

* Never reduce detail
* Never shorten instructions
* Never generalize
* The rewritten prompt must be at least as detailed as the original, preferably more

2. DO NOT REMOVE STRUCTURAL RIGOR
   The output MUST still include:

* A clear role definition at the top
* A CRITICAL RULES section
* Domain-specific extraction rules (adapted to the use case)
* A strict OUTPUT FORMAT section
* Explicit batching / ordering logic if present in the original

3. FULL CONTEXT ADAPTATION
   You MUST adapt the prompt to the user’s domain:

* Replace irrelevant sections with domain-relevant ones
* Add new sections if needed
* Remove only what is truly irrelevant, and replace it with something equally specific

Examples:

* Medical → emphasize anatomy, scans, labeling, spatial relationships
* Exams → emphasize problems, answer choices, solution steps
* Legal → emphasize clauses, definitions, structure, references
* Technical → emphasize equations, systems, diagrams

4. EXPAND DOMAIN-SPECIFIC DETAIL
   Add new rules that improve extraction quality for that use case:

* What to prioritize
* What to ignore (if applicable)
* How to interpret visuals in that domain
* What level of precision is required

5. PRESERVE STRICTNESS
   Maintain and reinforce language like:

* “Do NOT summarize”
* “Extract ALL content”
* “Preserve exact ordering”
* “Do NOT add outside knowledge”

6. OUTPUT FORMAT MUST BE EXPLICIT AND STRUCTURED

* Keep a numbered, repeatable structure per item (slide/page/etc.)
* Modify section names to match the use case
* Ensure every section has clear expectations

7. NO META COMMENTARY

* Do NOT explain what you changed
* Do NOT include reasoning
* Output ONLY the final rewritten prompt

8. MAINTAIN OPERATIONAL LOGIC
   If the original prompt includes:

* Batch size rules
* Ordering constraints
* Stopping conditions

These MUST remain unless the use case requires a clearly superior alternative.

9. LANGUAGE STYLE

* Use precise, directive language
* Avoid vague phrases like “be detailed”
* Instead specify exactly what must be extracted and how

10. LENGTH EXPECTATION
    The rewritten prompt should typically be:

* Equal length or longer than the original
* More specialized, not shorter

FINAL OUTPUT REQUIREMENT:

Return ONLY the fully rewritten prompt.

Do NOT include:

* Explanations
* Notes
* Comparisons
* Headings outside the prompt itself

The result must be immediately copy-paste usable as a standalone system prompt."""

PROMPT_BUILDER_STAGE_1_TIMEOUT_SECONDS = float(
    os.environ.get("SLIDEDROP_PROMPT_BUILDER_STAGE1_TIMEOUT_SECONDS", "90")
)
PROMPT_BUILDER_STAGE_2_TIMEOUT_SECONDS = float(
    os.environ.get("SLIDEDROP_PROMPT_BUILDER_STAGE2_TIMEOUT_SECONDS", "180")
)
PROMPT_BUILDER_MAX_TOKENS = int(
    os.environ.get("SLIDEDROP_PROMPT_BUILDER_MAX_TOKENS", "3200")
)
PROMPT_BUILDER_MODEL_CHOICE = os.environ.get(
    "SLIDEDROP_PROMPT_BUILDER_MODEL_CHOICE",
    DEFAULT_MODEL_CHOICE,
)
PROMPT_BUILDER_MODEL_NAME = os.environ.get(
    "SLIDEDROP_PROMPT_BUILDER_MODEL_NAME",
    "",
).strip()


class ExtractionStrategy(BaseModel):
    content_type: str
    primary_focus: list[str]
    secondary_focus: list[str]
    visual_handling: list[str]
    deprioritized_elements: list[str]
    output_structure_modifications: list[str]
    special_rules: list[str]


@dataclass(slots=True)
class PromptBuilderError(Exception):
    code: str
    message: str
    status_code: int = 500

    def __str__(self) -> str:
        return self.message


def _get_prompt_builder_model_name() -> str:
    if PROMPT_BUILDER_MODEL_NAME:
        return PROMPT_BUILDER_MODEL_NAME
    normalized_choice = normalize_model_choice(PROMPT_BUILDER_MODEL_CHOICE)
    return get_model_name(normalized_choice)


def _extract_json_blob(raw_text: str) -> str:
    stripped = raw_text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if match:
        return match.group(0)

    raise ValueError("No JSON object found in strategy response.")


def _parse_strategy(raw_text: str) -> ExtractionStrategy:
    try:
        payload = json.loads(_extract_json_blob(raw_text))
    except Exception as exc:
        raise ValueError(f"Malformed strategy JSON: {exc}") from exc

    try:
        return ExtractionStrategy.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Strategy JSON missing required fields: {exc}") from exc


def _humanize(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("_", " ").replace("-", " ")).strip()


def _strip_model_echoes(prompt_text: str) -> str:
    cleaned = prompt_text.strip()
    markers = ("\nDEFAULT PROMPT:", "\nEXTRACTION STRATEGY:", "\nUSE CASE:")
    cut_points = [cleaned.find(marker) for marker in markers if cleaned.find(marker) > 0]
    if cut_points:
        cleaned = cleaned[: min(cut_points)].rstrip()
    return cleaned


def _normalized_for_similarity(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _looks_like_unchanged_baseline(prompt_text: str) -> bool:
    similarity = difflib.SequenceMatcher(
        None,
        _normalized_for_similarity(prompt_text),
        _normalized_for_similarity(AUTHORITATIVE_DEFAULT_PROMPT),
    ).ratio()
    return similarity >= 0.94


def _validate_compiled_prompt(prompt_text: str, use_case: str) -> str:
    cleaned = _strip_model_echoes(prompt_text)
    lowered = cleaned.lower()

    if not cleaned:
        raise ValueError("Prompt compiler returned an empty prompt.")
    if len(cleaned) < int(len(AUTHORITATIVE_DEFAULT_PROMPT.strip()) * 0.9):
        raise ValueError("Generated prompt is materially shorter than the default quality baseline.")
    if "default prompt:" in lowered or "extraction strategy:" in lowered:
        raise ValueError("Generated prompt echoed internal compiler inputs.")
    if "critical rules" not in lowered:
        raise ValueError("Generated prompt is missing a CRITICAL RULES section.")
    if "output format" not in lowered:
        raise ValueError("Generated prompt is missing an OUTPUT FORMAT section.")
    if "do not summarize" not in lowered:
        raise ValueError("Generated prompt lost the no-summarization guardrail.")
    if "outside knowledge" not in lowered:
        raise ValueError("Generated prompt lost the outside-knowledge restriction.")
    if "batch" not in lowered or "wait" not in lowered:
        raise ValueError("Generated prompt lost the batch or stopping behavior.")
    if lowered.startswith("here is") or lowered.startswith("below is"):
        raise ValueError("Generated prompt included meta commentary instead of prompt text only.")
    if _looks_like_unchanged_baseline(cleaned):
        raise ValueError(
            "Generated prompt stayed too close to the lecture baseline instead of refactoring for the new use case."
        )
    lowered_use_case = use_case.lower()
    if all(term not in lowered_use_case for term in ("lecture", "slide", "class", "course")):
        if "lecture extraction engine" in lowered or "slide [number]" in lowered:
            raise ValueError("Generated prompt kept lecture-specific wording for a non-lecture use case.")

    return cleaned


def _format_list(title: str, items: list[str]) -> str:
    normalized_items = [_humanize(item) for item in items if _humanize(item)]
    if not normalized_items:
        normalized_items = ["Not specified"]
    lines = [title]
    lines.extend(f"• {item}" for item in normalized_items)
    return "\n".join(lines)


def _compile_prompt_fallback(use_case: str, strategy: ExtractionStrategy) -> str:
    """Deterministic fallback compiler that preserves the baseline rigor floor.

    The two-stage Ollama pipeline remains the primary path. This fallback exists so
    a bad compiler response never pollutes the editor with echoed JSON or an unchanged
    lecture prompt. It refactors the lecture baseline using the structured strategy.
    """
    content_type = _humanize(strategy.content_type or "domain-specific document")
    primary_focus = [_humanize(item) for item in strategy.primary_focus if _humanize(item)]
    secondary_focus = [_humanize(item) for item in strategy.secondary_focus if _humanize(item)]
    visual_handling = [_humanize(item) for item in strategy.visual_handling if _humanize(item)]
    deprioritized = [_humanize(item) for item in strategy.deprioritized_elements if _humanize(item)]
    output_mods = [
        _humanize(item) for item in strategy.output_structure_modifications if _humanize(item)
    ]
    special_rules = [_humanize(item) for item in strategy.special_rules if _humanize(item)]

    primary_focus_text = "\n".join(f"• {item}" for item in (primary_focus or ["All domain-critical content"]))
    secondary_focus_text = "\n".join(
        f"• {item}" for item in (secondary_focus or ["Supporting domain details and contextual references"])
    )
    visual_handling_text = "\n".join(
        f"• {item}" for item in (visual_handling or ["Describe every meaningful visual element with exact visible detail"])
    )
    deprioritized_text = "\n".join(
        f"• {item}" for item in (deprioritized or ["Do not spend space on decorative elements unless they change meaning"])
    )
    output_mods_text = "\n".join(
        f"• {item}" for item in (output_mods or ["Keep a rigid item-by-item structure with domain-specific section labels"])
    )
    special_rules_text = "\n".join(
        f"• {item}" for item in (special_rules or ["Apply any domain-specific precision requirements implied by the material"])
    )

    return f"""You are my {content_type} extraction engine.

I will upload 10 images at a time. I will provide a range (e.g., "Items 11–20"). You must assume the first image uploaded is the first number in that range, and they follow in perfect chronological order. Your job is to extract ALL domain-relevant content in extreme detail for this use case: {use_case}. The output must be precise enough that I can paste it into another AI that cannot accept images.

CRITICAL RULES

Do NOT summarize, shorten, or simplify.

Do NOT add outside knowledge.

Preserve exact ordering exactly as mapped to the range I provide.

Work in batches of EXACTLY 10 images.

After finishing each batch, STOP and wait for me to provide the next range and set of images.

If there are fewer than 10 images remaining in the final batch, label it “FINAL BATCH.”

Extract exact wording, labels, numbers, symbols, and visible structure whenever they are readable.

If something is uncertain, mark it explicitly as unclear rather than guessing.

DOMAIN PRIORITY RULES

PRIMARY FOCUS
{primary_focus_text}

SECONDARY FOCUS
{secondary_focus_text}

VISUAL HANDLING RULES

• Extract ALL visible text from images using OCR.
• If an image contains screenshots, diagrams, handwritten notes, scans, labels, stamps, or embedded panels, transcribe every readable word.
• When visuals carry meaning, describe exactly what is visible, how elements are arranged, what labels or markers appear, and what conclusion the source material is making.
{visual_handling_text}

DEPRIORITIZATION RULES

{deprioritized_text}

SPECIAL RULES

{special_rules_text}

OUTPUT FORMAT ADAPTATIONS

{output_mods_text}

OUTPUT FORMAT (MANDATORY STRUCTURE)

For each item, use this exact structure:

Item [Number]: [Exact Visible Title / Best Available Heading]

1. FULL RAW TEXT

All headings, bullets, sub-bullets, footnotes, captions, labels, annotations, OCR text, and any other readable text visible in the image.

2. PRIMARY CONTENT

Focus Area:

Exact extracted details:

Context / Importance:

3. SECONDARY DETAILS

Supporting details:

References / qualifiers / dependencies:

4. VISUAL ELEMENTS / FIGURES / TABLES / LAYOUT

Type:

Full visual description:

Labels / values / relationships:

Domain-specific takeaway:

5. STRUCTURE / FINDINGS / APPLICATIONS / REFERENCES

Domain-specific elements:

Step-by-step logic, comparisons, findings, clauses, worked steps, or interpretive structure shown in the image:

6. SPECIAL FLAGS

Ambiguities:

Unclear text:

Critical constraints or warnings shown in the source:

After completing the 10th item of the batch, end with:

END OF BATCH (Items X–Y). Please provide the next range and upload the next 10 images.

Then wait."""


async def _generate_with_ollama(
    *,
    system_prompt: str,
    user_prompt: str,
    timeout_seconds: float,
    model_name: str,
    expect_json: bool = False,
) -> str:
    payload: dict[str, Any] = {
        "model": model_name,
        "system": system_prompt,
        "prompt": user_prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": PROMPT_BUILDER_MAX_TOKENS,
        },
    }
    if expect_json:
        payload["format"] = "json"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                OLLAMA_URL,
                json=payload,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise PromptBuilderError(
            code="ollama_timeout",
            message="Ollama took too long to generate the prompt.",
            status_code=504,
        ) from exc
    except httpx.HTTPError as exc:
        raise PromptBuilderError(
            code="ollama_unavailable",
            message="Ollama is unavailable. Make sure it is installed and running locally.",
            status_code=503,
        ) from exc

    data = response.json()
    text = data.get("response", "")
    if not isinstance(text, str) or not text.strip():
        raise PromptBuilderError(
            code="ollama_empty_response",
            message="Ollama returned an empty response while building the prompt.",
            status_code=502,
        )
    return text.strip()


async def _run_stage_1(use_case: str, model_name: str) -> ExtractionStrategy:
    user_message = f"USE CASE:\n{use_case}"
    errors: list[str] = []

    for _ in range(2):
        raw_response = await _generate_with_ollama(
            system_prompt=STAGE_1_SYSTEM_PROMPT,
            user_prompt=user_message,
            timeout_seconds=PROMPT_BUILDER_STAGE_1_TIMEOUT_SECONDS,
            model_name=model_name,
            expect_json=True,
        )
        try:
            return _parse_strategy(raw_response)
        except ValueError as exc:
            errors.append(str(exc))

    raise PromptBuilderError(
        code="strategy_invalid",
        message="Ollama returned malformed strategy JSON twice while building the custom prompt.",
        status_code=502,
    )


async def _run_stage_2(strategy: ExtractionStrategy, model_name: str, use_case: str) -> str:
    strategy_json = json.dumps(strategy.model_dump(), ensure_ascii=False, indent=2)
    user_message = (
        f"DEFAULT PROMPT:\n{AUTHORITATIVE_DEFAULT_PROMPT}\n\n"
        f"EXTRACTION STRATEGY:\n{strategy_json}"
    )

    errors: list[str] = []
    for _ in range(2):
        raw_prompt = await _generate_with_ollama(
            system_prompt=STAGE_2_SYSTEM_PROMPT,
            user_prompt=user_message,
            timeout_seconds=PROMPT_BUILDER_STAGE_2_TIMEOUT_SECONDS,
            model_name=model_name,
        )
        try:
            return _validate_compiled_prompt(raw_prompt, use_case)
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        return _compile_prompt_fallback(use_case, strategy)

    raise PromptBuilderError(
        code="prompt_compilation_failed",
        message="Ollama could not produce a prompt that preserved the default baseline rigor.",
        status_code=502,
    )


async def generate_custom_prompt(use_case: str) -> str:
    normalized_use_case = use_case.strip()
    if not normalized_use_case:
        raise PromptBuilderError(
            code="empty_use_case",
            message="Describe what you want the extraction engine to be used for.",
            status_code=400,
        )

    model_name = _get_prompt_builder_model_name()
    started_ollama_here = False
    await asyncio.to_thread(_extraction_lock.acquire)

    try:
        try:
            started_ollama_here = await asyncio.to_thread(_start_ollama)
            await asyncio.to_thread(_clear_loaded_models)
            await asyncio.to_thread(_ensure_model_available, model_name)
        except Exception as exc:
            raise PromptBuilderError(
                code="ollama_unavailable",
                message="Ollama is unavailable. Make sure it is installed and ready on this Mac.",
                status_code=503,
            ) from exc

        strategy = await _run_stage_1(normalized_use_case, model_name)
        return await _run_stage_2(strategy, model_name, normalized_use_case)
    finally:
        if started_ollama_here:
            await asyncio.to_thread(_stop_ollama)
        _extraction_lock.release()

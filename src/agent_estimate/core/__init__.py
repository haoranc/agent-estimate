"""Core estimation models and algorithms."""

from agent_estimate.core.human_comparison import compute_human_equivalent, get_human_multiplier
from agent_estimate.core.models import (
    AgentProfile,
    AgentProfileProtocol,
    EstimationConfig,
    MetrWarning,
    ModifierSet,
    PertResult,
    ProjectSettings,
    ReviewMode,
    SizeTier,
    SizingResult,
    TaskEstimate,
    TaskNode,
    TaskType,
    Wave,
    WaveAssignment,
    WavePlan,
)
from agent_estimate.core.history import WarmContextResult, infer_warm_context
from agent_estimate.core.modifiers import (
    apply_modifiers,
    build_modifier_set,
    compute_review_overhead,
)
from agent_estimate.core.pert import (
    check_metr_threshold,
    compute_pert,
    estimate_task,
    load_metr_thresholds,
)
from agent_estimate.core.sizing import TierCorrection, auto_correct_tier, classify_task
from agent_estimate.core.wave_planner import plan_waves

__all__ = [
    "AgentProfile",
    "AgentProfileProtocol",
    "EstimationConfig",
    "MetrWarning",
    "ModifierSet",
    "PertResult",
    "ProjectSettings",
    "ReviewMode",
    "SizeTier",
    "SizingResult",
    "TaskEstimate",
    "TaskNode",
    "TaskType",
    "Wave",
    "WaveAssignment",
    "WarmContextResult",
    "WavePlan",
    "apply_modifiers",
    "build_modifier_set",
    "check_metr_threshold",
    "TierCorrection",
    "auto_correct_tier",
    "classify_task",
    "compute_human_equivalent",
    "compute_pert",
    "compute_review_overhead",
    "estimate_task",
    "get_human_multiplier",
    "infer_warm_context",
    "load_metr_thresholds",
    "plan_waves",
]

"""Tests for core/task_type_models.py — non-coding estimation models."""

from __future__ import annotations

from agent_estimate.core.models import EstimationCategory, ReviewMode
from agent_estimate.core.modifiers import build_modifier_set
from agent_estimate.core.task_type_models import (
    _BRAINSTORM_BASELINES,
    _CONFIG_SRE_BASELINES,
    _DOCUMENTATION_BASELINES,
    _RESEARCH_BASELINES_DEEP,
    _RESEARCH_BASELINES_SHALLOW,
    detect_estimation_category,
    estimate_brainstorm,
    estimate_config_sre,
    estimate_documentation,
    estimate_research,
)


# ---------------------------------------------------------------------------
# detect_estimation_category
# ---------------------------------------------------------------------------


class TestDetectEstimationCategory:
    def test_default_is_coding(self) -> None:
        assert detect_estimation_category("Fix the login bug") == EstimationCategory.CODING

    def test_empty_string_is_coding(self) -> None:
        assert detect_estimation_category("") == EstimationCategory.CODING

    def test_whitespace_is_coding(self) -> None:
        assert detect_estimation_category("   ") == EstimationCategory.CODING

    # Brainstorm
    def test_brainstorm_keyword(self) -> None:
        assert detect_estimation_category("Brainstorm ideas for the new dashboard") == EstimationCategory.BRAINSTORM

    def test_spike_keyword(self) -> None:
        assert detect_estimation_category("Spike: explore auth options") == EstimationCategory.BRAINSTORM

    def test_discovery_keyword(self) -> None:
        assert detect_estimation_category("Discovery session for API design") == EstimationCategory.BRAINSTORM

    def test_sync_keyword(self) -> None:
        # "Team sync" alone is ambiguous — tightened pattern requires brainstorm context
        assert detect_estimation_category("Brainstorm sync on architecture direction") == EstimationCategory.BRAINSTORM
        # Plain "team sync" falls through to coding (no longer matched as brainstorm)
        assert detect_estimation_category("Team sync on architecture direction") == EstimationCategory.CODING

    def test_whiteboard_keyword(self) -> None:
        assert detect_estimation_category("Whiteboard the new data model") == EstimationCategory.BRAINSTORM

    # Research
    def test_research_keyword(self) -> None:
        assert detect_estimation_category("Research best practices for rate limiting") == EstimationCategory.RESEARCH

    def test_investigate_keyword(self) -> None:
        assert detect_estimation_category("Investigate why requests are slow") == EstimationCategory.RESEARCH

    def test_evaluate_keyword(self) -> None:
        assert detect_estimation_category("Evaluate OSS libraries for PDF generation") == EstimationCategory.RESEARCH

    def test_feasibility_keyword(self) -> None:
        assert detect_estimation_category("Feasibility study for new payment provider") == EstimationCategory.RESEARCH

    def test_benchmark_keyword(self) -> None:
        assert detect_estimation_category("Benchmarks for cache hit rates") == EstimationCategory.RESEARCH

    # Config / SRE
    def test_configure_keyword(self) -> None:
        assert detect_estimation_category("Configure nginx reverse proxy") == EstimationCategory.CONFIG_SRE

    def test_deploy_keyword(self) -> None:
        assert detect_estimation_category("Deploy staging environment") == EstimationCategory.CONFIG_SRE

    def test_terraform_keyword(self) -> None:
        assert detect_estimation_category("Terraform the new VPC") == EstimationCategory.CONFIG_SRE

    def test_kubernetes_keyword(self) -> None:
        assert detect_estimation_category("Kubernetes pod scaling config") == EstimationCategory.CONFIG_SRE

    def test_monitoring_keyword(self) -> None:
        assert detect_estimation_category("Set up monitoring and alerting for API") == EstimationCategory.CONFIG_SRE

    def test_cicd_keyword(self) -> None:
        assert detect_estimation_category("CI/CD pipeline for frontend") == EstimationCategory.CONFIG_SRE

    # Documentation
    def test_documentation_keyword(self) -> None:
        assert detect_estimation_category("Write documentation for new API") == EstimationCategory.DOCUMENTATION

    def test_readme_keyword(self) -> None:
        assert detect_estimation_category("Update README with setup instructions") == EstimationCategory.DOCUMENTATION

    def test_changelog_keyword(self) -> None:
        assert detect_estimation_category("Write changelog entry for v2.0") == EstimationCategory.DOCUMENTATION

    def test_api_docs_keyword(self) -> None:
        assert detect_estimation_category("Generate api docs for auth module") == EstimationCategory.DOCUMENTATION

    def test_case_insensitive(self) -> None:
        assert detect_estimation_category("BRAINSTORM new features") == EstimationCategory.BRAINSTORM
        assert detect_estimation_category("RESEARCH competitors") == EstimationCategory.RESEARCH


# ---------------------------------------------------------------------------
# estimate_brainstorm
# ---------------------------------------------------------------------------


class TestEstimateBrainstorm:
    def setup_method(self) -> None:
        self.modifiers = build_modifier_set()

    def test_returns_brainstorm_category(self) -> None:
        est = estimate_brainstorm("Brainstorm ideas", self.modifiers)
        assert est.estimation_category == EstimationCategory.BRAINSTORM

    def test_uses_brainstorm_baselines(self) -> None:
        est = estimate_brainstorm("Brainstorm ideas", self.modifiers)
        o, m, p = _BRAINSTORM_BASELINES
        assert est.sizing.baseline_optimistic == o
        assert est.sizing.baseline_most_likely == m
        assert est.sizing.baseline_pessimistic == p

    def test_expected_in_range(self) -> None:
        est = estimate_brainstorm("Brainstorm ideas", self.modifiers)
        # Expected should be around 5-15m for unit modifier
        assert 5.0 <= est.total_expected_minutes <= 20.0

    def test_default_review_is_none(self) -> None:
        est = estimate_brainstorm("Brainstorm ideas", self.modifiers)
        assert est.review_minutes == 0.0

    def test_review_mode_applied(self) -> None:
        est = estimate_brainstorm(
            "Brainstorm ideas", self.modifiers, review_mode=ReviewMode.STANDARD
        )
        assert est.review_minutes == 15.0

    def test_modifiers_reduce_time(self) -> None:
        cold_modifiers = build_modifier_set(warm_context=1.15)
        warm_modifiers = build_modifier_set(warm_context=0.3)
        cold_est = estimate_brainstorm("Brainstorm ideas", cold_modifiers)
        warm_est = estimate_brainstorm("Brainstorm ideas", warm_modifiers)
        assert warm_est.total_expected_minutes < cold_est.total_expected_minutes

    def test_no_metr_warning_for_short_task(self) -> None:
        est = estimate_brainstorm("Brainstorm ideas", self.modifiers)
        assert est.metr_warning is None

    def test_human_equivalent_passthrough(self) -> None:
        est = estimate_brainstorm("Brainstorm ideas", self.modifiers, human_equivalent_minutes=30.0)
        assert est.human_equivalent_minutes == 30.0

    def test_signal_label_in_sizing(self) -> None:
        est = estimate_brainstorm("Brainstorm ideas", self.modifiers)
        assert "brainstorm-flat-model" in est.sizing.signals


# ---------------------------------------------------------------------------
# estimate_research
# ---------------------------------------------------------------------------


class TestEstimateResearch:
    def setup_method(self) -> None:
        self.modifiers = build_modifier_set()

    def test_returns_research_category(self) -> None:
        est = estimate_research("Research options", self.modifiers)
        assert est.estimation_category == EstimationCategory.RESEARCH

    def test_shallow_research_uses_shallow_baselines(self) -> None:
        est = estimate_research("Research options", self.modifiers)
        o, m, p = _RESEARCH_BASELINES_SHALLOW
        assert est.sizing.baseline_optimistic == o
        assert est.sizing.baseline_most_likely == m
        assert est.sizing.baseline_pessimistic == p
        assert "research-shallow-model" in est.sizing.signals

    def test_deep_research_uses_deep_baselines(self) -> None:
        est = estimate_research("Comprehensive in-depth research", self.modifiers)
        o, m, p = _RESEARCH_BASELINES_DEEP
        assert est.sizing.baseline_optimistic == o
        assert est.sizing.baseline_most_likely == m
        assert est.sizing.baseline_pessimistic == p
        assert "research-deep-model" in est.sizing.signals

    def test_deep_triggers_on_thorough(self) -> None:
        est = estimate_research("Thorough analysis of competitors", self.modifiers)
        assert "research-deep-model" in est.sizing.signals

    def test_deep_triggers_on_extensive(self) -> None:
        est = estimate_research("Extensive literature review", self.modifiers)
        assert "research-deep-model" in est.sizing.signals

    def test_shallow_expected_in_range(self) -> None:
        est = estimate_research("Quick research", self.modifiers)
        assert 10.0 <= est.total_expected_minutes <= 35.0

    def test_deep_expected_in_range(self) -> None:
        est = estimate_research("Deep comprehensive review", self.modifiers)
        assert 25.0 <= est.total_expected_minutes <= 55.0

    def test_default_review_is_none(self) -> None:
        est = estimate_research("Research", self.modifiers)
        assert est.review_minutes == 0.0

    def test_deep_is_larger_than_shallow(self) -> None:
        shallow = estimate_research("Research options", self.modifiers)
        deep = estimate_research("Comprehensive thorough research", self.modifiers)
        assert deep.total_expected_minutes > shallow.total_expected_minutes


# ---------------------------------------------------------------------------
# estimate_config_sre
# ---------------------------------------------------------------------------


class TestEstimateConfigSre:
    def setup_method(self) -> None:
        self.modifiers = build_modifier_set()

    def test_returns_config_sre_category(self) -> None:
        est = estimate_config_sre("Configure nginx", self.modifiers)
        assert est.estimation_category == EstimationCategory.CONFIG_SRE

    def test_uses_config_sre_baselines(self) -> None:
        est = estimate_config_sre("Configure nginx", self.modifiers)
        o, m, p = _CONFIG_SRE_BASELINES
        assert est.sizing.baseline_optimistic == o
        assert est.sizing.baseline_most_likely == m
        assert est.sizing.baseline_pessimistic == p

    def test_expected_in_range(self) -> None:
        est = estimate_config_sre("Configure nginx", self.modifiers)
        assert 10.0 <= est.total_expected_minutes <= 40.0

    def test_signal_label_in_sizing(self) -> None:
        est = estimate_config_sre("Configure nginx", self.modifiers)
        assert "config-sre-flat-model" in est.sizing.signals

    def test_default_review_is_none(self) -> None:
        est = estimate_config_sre("Configure nginx", self.modifiers)
        assert est.review_minutes == 0.0

    def test_review_mode_applied(self) -> None:
        est = estimate_config_sre(
            "Configure nginx", self.modifiers, review_mode=ReviewMode.COMPLEX
        )
        assert est.review_minutes == 25.0


# ---------------------------------------------------------------------------
# estimate_documentation
# ---------------------------------------------------------------------------


class TestEstimateDocumentation:
    def setup_method(self) -> None:
        self.modifiers = build_modifier_set()

    def test_returns_documentation_category(self) -> None:
        est = estimate_documentation("Write API docs", self.modifiers)
        assert est.estimation_category == EstimationCategory.DOCUMENTATION

    def test_uses_documentation_baselines(self) -> None:
        est = estimate_documentation("Write API docs", self.modifiers)
        o, m, p = _DOCUMENTATION_BASELINES
        assert est.sizing.baseline_optimistic == o
        assert est.sizing.baseline_most_likely == m
        assert est.sizing.baseline_pessimistic == p

    def test_expected_in_range(self) -> None:
        est = estimate_documentation("Write API docs", self.modifiers)
        assert 10.0 <= est.total_expected_minutes <= 50.0

    def test_signal_label_in_sizing(self) -> None:
        est = estimate_documentation("Write API docs", self.modifiers)
        assert "documentation-model" in est.sizing.signals

    def test_default_review_is_none(self) -> None:
        est = estimate_documentation("Write API docs", self.modifiers)
        assert est.review_minutes == 0.0


# ---------------------------------------------------------------------------
# Pipeline integration: --type flag routes correctly
# ---------------------------------------------------------------------------


class TestPipelineRouting:
    """Integration-level: verify pipeline routes to correct model per category."""

    def setup_method(self) -> None:
        from agent_estimate.core.task_type_models import (
            _BRAINSTORM_BASELINES,
            _CONFIG_SRE_BASELINES,
            _DOCUMENTATION_BASELINES,
            _RESEARCH_BASELINES_SHALLOW,
        )
        from agent_estimate.core.sizing import TIER_BASELINES, SizeTier

        self.brainstorm_m = _BRAINSTORM_BASELINES[1]
        self.research_m = _RESEARCH_BASELINES_SHALLOW[1]
        self.config_m = _CONFIG_SRE_BASELINES[1]
        self.doc_m = _DOCUMENTATION_BASELINES[1]
        # Coding M baseline
        self.coding_m = TIER_BASELINES[SizeTier.M][1]

    def _run_pipeline(self, desc: str, category: EstimationCategory):
        from agent_estimate.cli.commands._pipeline import run_estimate_pipeline
        from agent_estimate.core.models import (
            AgentProfile,
            EstimationConfig,
            ProjectSettings,
            ReviewMode,
        )

        cfg = EstimationConfig(
            agents=[
                AgentProfile(
                    name="TestAgent",
                    capabilities=["coding"],
                    parallelism=1,
                    cost_per_turn=0.0,
                    model_tier="opus",
                )
            ],
            settings=ProjectSettings(
                friction_multiplier=1.0,
                inter_wave_overhead=0.0,
                review_overhead=0.0,
                metr_fallback_threshold=40.0,
            ),
        )
        return run_estimate_pipeline(
            [desc],
            cfg,
            review_mode=ReviewMode.NONE,
            task_category=category,
        )

    def test_brainstorm_category_produces_flat_model(self) -> None:
        report = self._run_pipeline("Do some work", EstimationCategory.BRAINSTORM)
        assert report.tasks[0].estimation_category == EstimationCategory.BRAINSTORM
        assert report.tasks[0].base_pert_most_likely_minutes == self.brainstorm_m

    def test_research_category_produces_research_model(self) -> None:
        report = self._run_pipeline("Do some work", EstimationCategory.RESEARCH)
        assert report.tasks[0].estimation_category == EstimationCategory.RESEARCH
        assert report.tasks[0].base_pert_most_likely_minutes == self.research_m

    def test_config_category_produces_config_model(self) -> None:
        report = self._run_pipeline("Do some work", EstimationCategory.CONFIG_SRE)
        assert report.tasks[0].estimation_category == EstimationCategory.CONFIG_SRE
        assert report.tasks[0].base_pert_most_likely_minutes == self.config_m

    def test_documentation_category_produces_doc_model(self) -> None:
        report = self._run_pipeline("Do some work", EstimationCategory.DOCUMENTATION)
        assert report.tasks[0].estimation_category == EstimationCategory.DOCUMENTATION
        assert report.tasks[0].base_pert_most_likely_minutes == self.doc_m

    def test_coding_category_uses_pert_tier_model(self) -> None:
        report = self._run_pipeline("Do some work", EstimationCategory.CODING)
        assert report.tasks[0].estimation_category == EstimationCategory.CODING
        # Coding uses PERT tier baselines, not flat model
        assert report.tasks[0].base_pert_most_likely_minutes == self.coding_m

    def test_auto_detection_brainstorm(self) -> None:
        report = self._run_pipeline("Brainstorm new feature ideas", None)
        assert report.tasks[0].estimation_category == EstimationCategory.BRAINSTORM

    def test_auto_detection_research(self) -> None:
        report = self._run_pipeline("Research caching solutions", None)
        assert report.tasks[0].estimation_category == EstimationCategory.RESEARCH

    def test_auto_detection_coding_default(self) -> None:
        report = self._run_pipeline("Fix the authentication bug", None)
        assert report.tasks[0].estimation_category == EstimationCategory.CODING

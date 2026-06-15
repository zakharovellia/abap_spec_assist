from tz_agents.section_writers.base import SectionWriter

SECTION_WRITERS: dict[str, SectionWriter] = {
    "header": SectionWriter("header", tier="small"),
    "business_context": SectionWriter("business_context", tier="medium"),
    "data_sources": SectionWriter("data_sources", tier="medium"),
    "selection_screen": SectionWriter("selection_screen", tier="medium"),
    "algorithm": SectionWriter(
        "algorithm",
        tier="strong",
        prompt_new="section_writers/algorithm_new.md",
        prompt_modification="section_writers/algorithm_modification.md",
    ),
    "output_layout": SectionWriter("output_layout", tier="medium"),
    "authorizations": SectionWriter("authorizations", tier="small"),
    "error_handling": SectionWriter("error_handling", tier="medium"),
    "test_cases": SectionWriter("test_cases", tier="medium"),
}

INDEPENDENT_SECTIONS: tuple[str, ...] = (
    "header",
    "business_context",
    "data_sources",
    "selection_screen",
    "output_layout",
    "authorizations",
)

DEPENDENT_SECTIONS: tuple[str, ...] = (
    "algorithm",
    "error_handling",
    "test_cases",
)

__all__ = ["SECTION_WRITERS", "INDEPENDENT_SECTIONS", "DEPENDENT_SECTIONS", "SectionWriter"]

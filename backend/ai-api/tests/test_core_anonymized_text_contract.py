from pathlib import Path


BACKEND_DIR = (
    Path(__file__).resolve().parents[2]
)

RAW_INPUT_PATH = (
    BACKEND_DIR
    / "core-api"
    / "src"
    / "main"
    / "java"
    / "com"
    / "aivle"
    / "bigproject"
    / "analysis"
    / "client"
    / "RawInputRequest.java"
)

SERVICE_PATH = (
    BACKEND_DIR
    / "core-api"
    / "src"
    / "main"
    / "java"
    / "com"
    / "aivle"
    / "bigproject"
    / "analysis"
    / "AiAnalysisService.java"
)


def test_core_raw_input_has_anonymized_text_field():
    source = RAW_INPUT_PATH.read_text(
        encoding="utf-8-sig"
    )

    assert "String anonymizedText" in source


def test_core_builds_anonymized_text_from_masked_arrays_only():
    source = SERVICE_PATH.read_text(
        encoding="utf-8-sig"
    )

    assert (
        "buildCombinedAnonymizedText(consultation)"
        in source
    )
    assert "getCallInputTextsMasked()" in source
    assert "getInpersonInputTextsMasked()" in source

    start = source.index(
        "private String buildCombinedAnonymizedText"
    )
    end = source.index(
        "private static List<String> nullSafe",
        start,
    )
    method = source[start:end]

    assert "getInputText()" not in method
    assert "getCallInputTexts()" not in method
    assert "getInpersonInputTexts()" not in method

import importlib.util
import json
from pathlib import Path


def _load_generator():
    path = Path(__file__).resolve().parents[1] / "scripts" / "build_emoji_catalog.py"
    spec = importlib.util.spec_from_file_location("build_emoji_catalog", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_emoji_catalog_generator_defaults_are_pinned() -> None:
    generator = _load_generator()

    assert generator.DEFAULT_EMOJI_VERSION == "17.0"
    assert len(generator.DEFAULT_CLDR_REF) == 40
    assert "/main/" not in generator.DEFAULT_ANNOTATIONS_URL
    assert "/main/" not in generator.DEFAULT_ANNOTATIONS_DERIVED_URL
    assert len(generator.DEFAULT_INPUT_SHA256) == 64
    assert len(generator.DEFAULT_ANNOTATIONS_SHA256) == 64
    assert len(generator.DEFAULT_ANNOTATIONS_DERIVED_SHA256) == 64
    assert generator.DEFAULT_KEYWORD_CACHE_PATH == generator.DEFAULT_OUTPUT_PATH


def test_keyword_cache_loads_only_stringy_non_empty_entries(tmp_path: Path) -> None:
    generator = _load_generator()
    cache_path = tmp_path / "catalog.json"
    cache_path.write_text(
        json.dumps(
            {
                "codepoint_keyword_map": {"1f600": " grin smile ", "": "drop"},
                "emoji_keyword_map": {"🇺🇸": " usa america ", "🎉": ""},
            }
        ),
        encoding="utf-8",
    )

    codepoint_keywords, emoji_keywords = generator.load_keyword_cache(str(cache_path))

    assert codepoint_keywords == {"1f600": "grin smile"}
    assert emoji_keywords == {"🇺🇸": "usa america"}


def test_keyword_tokens_fold_accents_for_ascii_search() -> None:
    generator = _load_generator()

    assert generator._keyword_tokens("Côte d’Ivoire São Tomé Åland Türkiye Curaçao") == [
        "cote",
        "ivoire",
        "sao",
        "tome",
        "aland",
        "turkiye",
        "curacao",
    ]


def test_build_catalog_uses_cached_keywords_when_annotations_are_unavailable() -> None:
    generator = _load_generator()
    sample = "\n".join(
        [
            "# emoji-test.txt",
            "# Date: 2025-08-04, 20:55:31 GMT",
            "# Version: 17.0",
            "# group: Smileys & Emotion",
            "1F600 ; fully-qualified # 😀 E1.0 grinning face",
            "# group: Flags",
            "1F1FA 1F1F8 ; fully-qualified # 🇺🇸 E2.0 flag: United States",
        ]
    )

    payload = generator.build_catalog(
        sample,
        annotations=None,
        cached_codepoint_keyword_map={"1f600": "grin smile happy"},
        cached_emoji_keyword_map={"🇺🇸": "flag usa america"},
    )

    assert payload["version"] == "17.0"
    assert payload["codepoint_keyword_map"]["1f600"] == "grin smile happy"
    assert payload["emoji_keyword_map"]["🇺🇸"] == "flag usa america"


def test_build_catalog_uses_cldr_annotations_when_available() -> None:
    generator = _load_generator()
    annotations = generator.parse_cldr_annotations(
        """
        <ldml>
          <annotations>
            <annotation cp="😀">face | grin | smile</annotation>
            <annotation cp="😀" type="tts">grinning face</annotation>
          </annotations>
        </ldml>
        """
    )
    sample = "\n".join(
        [
            "# emoji-test.txt",
            "# Date: 2025-08-04, 20:55:31 GMT",
            "# Version: 17.0",
            "# group: Smileys & Emotion",
            "1F600 ; fully-qualified # 😀 E1.0 grinning face",
        ]
    )

    payload = generator.build_catalog(sample, annotations=annotations)

    assert payload["codepoint_keyword_map"]["1f600"] == "grinning face grin smile"

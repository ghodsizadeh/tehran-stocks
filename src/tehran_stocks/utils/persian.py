"""Persian and Arabic text normalization utilities."""

from __future__ import annotations

_CHAR_TRANSLATION = str.maketrans(
    {
        "\u0643": "\u06a9",  # Arabic Kaf ك -> Persian Keheh ک
        "\u064a": "\u06cc",  # Arabic Yeh ي -> Persian Farsi Yeh ی
        "\u0649": "\u06cc",  # Arabic Alef Maksura ى -> Persian Farsi Yeh ی
        "\u0629": "\u0647",  # Arabic Teh Marbuta ة -> Heh ه
        # Persian digits ۰-۹ -> ASCII 0-9
        "\u06f0": "0",
        "\u06f1": "1",
        "\u06f2": "2",
        "\u06f3": "3",
        "\u06f4": "4",
        "\u06f5": "5",
        "\u06f6": "6",
        "\u06f7": "7",
        "\u06f8": "8",
        "\u06f9": "9",
        # Arabic-Indic digits ٠-٩ -> ASCII 0-9
        "\u0660": "0",
        "\u0661": "1",
        "\u0662": "2",
        "\u0663": "3",
        "\u0664": "4",
        "\u0665": "5",
        "\u0666": "6",
        "\u0667": "7",
        "\u0668": "8",
        "\u0669": "9",
    }
)

_ZERO_WIDTH_CHARS = str.maketrans(
    "",
    "",
    "\u200b\u200c\u200d\u200e\u200f\ufeff",
)


def normalize_persian(text: str) -> str:
    """Normalize Arabic/Persian character variants, digits, ZWNJ, and whitespace."""
    if not text:
        return ""
    normalized = text.translate(_CHAR_TRANSLATION).translate(_ZERO_WIDTH_CHARS)
    return " ".join(normalized.split())

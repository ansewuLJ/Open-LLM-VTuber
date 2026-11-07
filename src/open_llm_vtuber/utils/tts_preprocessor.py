import re
import unicodedata
from loguru import logger
from ..translate.translate_interface import TranslateInterface


def tts_filter(
    text: str,
    remove_special_char: bool,
    ignore_brackets: bool,
    ignore_parentheses: bool,
    ignore_asterisks: bool,
    ignore_angle_brackets: bool,
    translator: TranslateInterface | None = None,
) -> str:
    """
    Filter or do anything to the text before TTS generates the audio.
    Changes here do not affect subtitles or LLM's memory. The generated audio is
    the only affected thing.

    Args:
        text (str): The text to filter.
        remove_special_char (bool): Whether to remove special characters.
        ignore_brackets (bool): Whether to ignore text within brackets.
        ignore_parentheses (bool): Whether to ignore text within parentheses.
        ignore_asterisks (bool): Whether to ignore text within asterisks.
        translator (TranslateInterface, optional):
            The translator to use. If None, we'll skip the translation. Defaults to None.

    Returns:
        str: The filtered text.
    """
    # Markdown headings, bullets, blockquotes and inline code markers are not
    # speech; strip the markers but keep the text they decorate. This runs
    # before the filters below collapse newlines, otherwise line-start bullets
    # can no longer be identified.
    text = strip_markdown(text)

    if ignore_asterisks:
        try:
            text = filter_asterisks(text)
        except Exception as e:
            logger.warning(f"Error ignoring asterisks: {e}")
            logger.warning(f"Text: {text}")
            logger.warning("Skipping...")

    if ignore_brackets:
        try:
            text = filter_brackets(text)
        except Exception as e:
            logger.warning(f"Error ignoring brackets: {e}")
            logger.warning(f"Text: {text}")
            logger.warning("Skipping...")
    if ignore_parentheses:
        try:
            text = filter_parentheses(text)
        except Exception as e:
            logger.warning(f"Error ignoring parentheses: {e}")
            logger.warning(f"Text: {text}")
            logger.warning("Skipping...")
    if ignore_angle_brackets:
        try:
            text = filter_angle_brackets(text)
        except Exception as e:
            logger.warning(f"Error ignoring angle brackets: {e}")
            logger.warning(f"Text: {text}")
            logger.warning("Skipping...")

    if remove_special_char:
        try:
            text = remove_special_characters(text)
        except Exception as e:
            logger.warning(f"Error removing special characters: {e}")
            logger.warning(f"Text: {text}")
            logger.warning("Skipping...")
    if translator:
        try:
            logger.info("Translating...")
            text = translator.translate(text)
            logger.info(f"Translated: {text}")
        except Exception as e:
            logger.critical(f"Error translating: {e}")
            logger.critical(f"Text: {text}")
            logger.warning("Skipping...")

    logger.debug(f"Filtered text: {text}")
    return text


def strip_markdown(text: str) -> str:
    """Strip Markdown markers and symbols that are not speakable."""
    # Fenced code blocks are not useful in speech.
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    # Keep link text, drop the URL.
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Headings, blockquotes, bullets, numbered-list markers and rules.
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*>\s?", "", text)
    text = re.sub(r"(?m)^\s*[-*+]\s+", "", text)
    text = re.sub(r"(?m)^\s*\d+[.、)]\s+", "", text)
    text = re.sub(r"(?m)^\s*-{3,}\s*$", "", text)

    # Markdown table separator rows; then turn remaining pipes into pauses.
    text = re.sub(r"(?m)^\s*\|?[\s:|-]+\|?\s*$", "", text)
    text = text.replace("|", "，")

    # Arrows and common math/technical symbols that Breeze cannot read well.
    for arrow in ("→", "⇒", "➡", "➔", "->"):
        text = text.replace(arrow, "，然后，")
    for arrow in ("←", "⇐", "<-"):
        text = text.replace(arrow, "，来自，")
    text = text.replace("↑", "上升").replace("↓", "下降").replace("↔", "互相")
    text = text.replace("•", "，").replace("·", "，").replace("▪", "，").replace("◦", "，")
    text = text.replace("—", "，").replace("–", "，")
    text = text.replace("≈", "约等于").replace("≥", "大于等于").replace("≤", "小于等于")
    text = text.replace("≠", "不等于").replace("×", "乘以").replace("÷", "除以")
    text = text.replace("±", "正负").replace("℃", "摄氏度")
    text = text.replace("°F", "华氏度").replace("°C", "摄氏度")
    text = text.replace("°", "度")

    # Inline code backticks; keep the code text itself.
    text = text.replace("`", "")
    # Basic emoji removal; they have no spoken form.
    text = re.sub(r"[\U0001F300-\U0001FAFF☀-➿]", "", text)

    # Collapse punctuation introduced by the replacements.
    text = re.sub(r"[,，]{2,}", "，", text)
    text = re.sub(r"，([。！？；：])", r"\1", text)
    text = re.sub(r"\s+([，。！？；：、])", r"\1", text)
    text = re.sub(r"([，。！？；：、])\s+", r"\1", text)
    return text.strip()


def remove_special_characters(text: str) -> str:
    """
    Filter text to remove all non-letter, non-number, and non-punctuation characters.

    Args:
        text (str): The text to filter.

    Returns:
        str: The filtered text.
    """
    normalized_text = unicodedata.normalize("NFKC", text)

    def is_valid_char(char: str) -> bool:
        category = unicodedata.category(char)
        return (
            category.startswith("L")
            or category.startswith("N")
            or category.startswith("P")
            or char.isspace()
        )

    filtered_text = "".join(char for char in normalized_text if is_valid_char(char))
    return filtered_text


def _filter_nested(text: str, left: str, right: str) -> str:
    """
    Generic function to handle nested symbols.

    Args:
        text (str): The text to filter.
        left (str): The left symbol (e.g. '[' or '(').
        right (str): The right symbol (e.g. ']' or ')').

    Returns:
        str: The filtered text.
    """
    if not isinstance(text, str):
        raise TypeError("Input must be a string")
    if not text:
        return text

    result = []
    depth = 0
    for char in text:
        if char == left:
            depth += 1
        elif char == right:
            if depth > 0:
                depth -= 1
        else:
            if depth == 0:
                result.append(char)
    filtered_text = "".join(result)
    filtered_text = re.sub(r"\s+", " ", filtered_text).strip()
    return filtered_text


def filter_brackets(text: str) -> str:
    """
    Filter text to remove all text within brackets, handling nested cases.

    Args:
        text (str): The text to filter.

    Returns:
        str: The filtered text.
    """
    return _filter_nested(text, "[", "]")


def filter_parentheses(text: str) -> str:
    """
    Filter text to remove all text within parentheses, handling nested cases.

    Args:
        text (str): The text to filter.

    Returns:
        str: The filtered text.
    """
    return _filter_nested(text, "(", ")")


def filter_angle_brackets(text: str) -> str:
    """
    Filter text to remove all text within angle brackets, handling nested cases.

    Args:
        text (str): The text to filter.

    Returns:
        str: The filtered text.
    """
    return _filter_nested(text, "<", ">")


def filter_asterisks(text: str) -> str:
    """
    Handle Markdown emphasis and roleplay actions.

    Double/triple asterisks are Markdown bold/italic: keep the text and drop
    only the markers, otherwise headings such as **解析过程** disappear from
    the spoken output. Single-asterisk spans are treated as roleplay actions
    and removed, preserving the previous behaviour for *smiles* style text.

    Args:
        text: The input string.

    Returns:
        The string with Markdown markers removed and roleplay actions dropped.
    """
    # Keep the content of Markdown bold/italic spans.
    filtered_text = re.sub(r"\*{3}(.+?)\*{3}", r"\1", text, flags=re.S)
    filtered_text = re.sub(r"\*{2}(.+?)\*{2}", r"\1", filtered_text, flags=re.S)
    # Single-asterisk actions are not meant to be spoken.
    filtered_text = re.sub(r"\*([^*]+)\*", "", filtered_text)
    filtered_text = re.sub(r"\*+", "", filtered_text)

    # Clean up any extra spaces
    filtered_text = re.sub(r"\s+", " ", filtered_text).strip()

    return filtered_text

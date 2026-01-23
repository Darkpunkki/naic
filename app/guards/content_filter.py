"""
Content Filter - Sanitization and prompt injection protection for LLM inputs.
"""
import re
from typing import Optional


class ContentFilterError(Exception):
    """Raised when content fails security checks."""

    def __init__(self, message: str = "Your input contains disallowed content. Please rephrase and try again."):
        self.message = message
        super().__init__(self.message)


class ContentFilter:
    """
    Content filter for sanitizing user inputs before sending to LLM.

    Protects against:
    - Prompt injection attacks
    - Malicious special characters
    """

    # Patterns that indicate prompt injection attempts
    INJECTION_PATTERNS = [
        # Direct instruction overrides
        r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)",
        r"disregard\s+(all\s+)?(previous|prior|above|everything)",
        r"forget\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?)",
        r"override\s+(all\s+)?(previous|prior)\s+(instructions?|prompts?)",
        r"new\s+instructions?:",
        r"system\s*prompt:",
        r"you\s+are\s+now\s+(a|an)\s+",
        r"pretend\s+(you\s+are|to\s+be)",
        r"act\s+as\s+(if|a|an)",
        r"roleplay\s+as",

        # System/role markers (various LLM formats)
        r"\[INST\]",
        r"\[/INST\]",
        r"<<SYS>>",
        r"<</SYS>>",
        r"<\|system\|>",
        r"<\|user\|>",
        r"<\|assistant\|>",
        r"### (System|User|Assistant|Human|AI):",
        r"\[System\]",
        r"\[Human\]",
        r"\[Assistant\]",

        # Jailbreak attempts
        r"DAN\s*mode",
        r"developer\s*mode",
        r"jailbreak",
        r"bypass\s+(safety|content|filter)",
    ]

    # Characters to remove from free-text fields
    UNSAFE_CHARS = r'[<>{}\[\]\\`]'

    @classmethod
    def check_injection(cls, text: str) -> bool:
        """
        Check if text contains prompt injection patterns.

        Returns:
            True if injection detected, False otherwise
        """
        if not text:
            return False

        text_lower = text.lower()

        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True

        return False

    @classmethod
    def sanitize(cls, text: str) -> str:
        """
        Sanitize text by removing unsafe characters and normalizing whitespace.

        Args:
            text: Input text to sanitize

        Returns:
            Sanitized text
        """
        if not text:
            return ""

        # Remove unsafe characters
        text = re.sub(cls.UNSAFE_CHARS, '', text)

        # Normalize whitespace (collapse multiple spaces, trim)
        text = ' '.join(text.split())

        return text.strip()

    @classmethod
    def filter_input(cls, text: str, field_name: str = "input") -> str:
        """
        Full filter pipeline: check for injection, then sanitize.

        Args:
            text: Input text to filter
            field_name: Name of field for error messages

        Returns:
            Sanitized text

        Raises:
            ContentFilterError: If prompt injection is detected
        """
        if not text:
            return ""

        # Check for injection attempts
        if cls.check_injection(text):
            raise ContentFilterError(
                f"Your {field_name} contains disallowed content. "
                "Please remove any special instructions and try again."
            )

        # Sanitize the text
        return cls.sanitize(text)

    @classmethod
    def filter_workout_inputs(
        cls,
        target: Optional[str] = None,
        restrictions: Optional[str] = None,
        movement_name: Optional[str] = None
    ) -> dict:
        """
        Filter all workout-related inputs.

        Returns:
            dict with filtered values

        Raises:
            ContentFilterError: If any input fails security checks
        """
        result = {}

        if target is not None:
            result['target'] = cls.filter_input(target, "workout target")

        if restrictions is not None:
            result['restrictions'] = cls.filter_input(restrictions, "restrictions")

        if movement_name is not None:
            result['movement_name'] = cls.filter_input(movement_name, "movement name")

        return result

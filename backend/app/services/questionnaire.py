"""The wizard's questions for each category (architecture sections 7.2 and 7.3).

Answer ids match the ``answer_modifiers`` keys in ``config/categories/*.yaml`` (for example
``target_customer.students`` or ``is_24x7.yes``), so an answer the user gives can change the
landmark weights. Questions that no config uses yet (format, opening hours) are still collected and
stored with the analysis.
"""

from __future__ import annotations

from typing import Any

TARGET_CUSTOMER = {
    "id": "target_customer",
    "label": "Who do you want to serve?",
    "type": "multi",
    "options": [
        {"value": "students", "label": "Students"},
        {"value": "young_professionals", "label": "Young professionals"},
        {"value": "families", "label": "Families"},
        {"value": "seniors", "label": "Seniors"},
        {"value": "tourists", "label": "Tourists"},
    ],
}
YES_NO = [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]

QUESTIONS: dict[str, list[dict[str, Any]]] = {
    "cafe": [
        TARGET_CUSTOMER,
        {
            "id": "format",
            "label": "What format do you plan?",
            "type": "single",
            "options": [
                {"value": "takeaway", "label": "Takeaway kiosk"},
                {"value": "sit_down", "label": "Sit-down cafe"},
                {"value": "coworking", "label": "Co-working style"},
            ],
        },
    ],
    "clothing": [
        TARGET_CUSTOMER,
        {
            "id": "segment",
            "label": "Which segment?",
            "type": "single",
            "options": [
                {"value": "men", "label": "Men"},
                {"value": "women", "label": "Women"},
                {"value": "kids", "label": "Kids"},
                {"value": "ethnic", "label": "Ethnic"},
                {"value": "multi", "label": "Multi-segment"},
            ],
        },
        {
            "id": "needs_parking",
            "label": "Do you need parking?",
            "type": "single",
            "options": YES_NO,
        },
    ],
    "pharmacy": [
        TARGET_CUSTOMER,
        {"id": "is_24x7", "label": "Open 24x7?", "type": "single", "options": YES_NO},
        {
            "id": "nearby_clinics",
            "label": "Is being near clinics and labs acceptable?",
            "type": "single",
            "options": YES_NO,
        },
    ],
}


def questions_for(category: str) -> list[dict[str, Any]]:
    """The questions for a category (empty for an unknown one)."""
    return QUESTIONS.get(category, [])

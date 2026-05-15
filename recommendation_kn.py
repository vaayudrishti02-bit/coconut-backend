# recommendation_kn.py
# Kannada translations for Coconut Tree Illness Recommendations

from typing import Dict, Any

# Disease name translations
DISEASE_NAMES_KN = {
    "Bud Rot": "ಮೊಗ್ಗು ಕೊಳೆತ",
    "Bud Rot Dropping": "ಮೊಗ್ಗು ಕೊಳೆತ ಉದುರುವಿಕೆ",
    "Grey Leaf Rot": "ಬೂದು ಎಲೆ ಕೊಳೆತ",
    "Leaf Rot": "ಎಲೆ ಕೊಳೆತ",
    "Stem Bleeding": "ಕಾಂಡ ರಕ್ತಸ್ರಾವ",
    "Whitefly": "ಬಿಳಿ ನೊಣ",
    "Healthy": "ಆರೋಗ್ಯಕರ",
    "Unknown": "ಅಜ್ಞಾತ",
}

# Status translations
STATUS_KN = {
    "healthy": "ಆರೋಗ್ಯಕರ",
    "illness": "ರೋಗ",
    "unknown": "ಅಜ್ಞಾತ",
}

# Severity translations
SEVERITY_KN = {
    "mild": "ಸೌಮ್ಯ",
    "medium": "ಮಧ್ಯಮ",
    "severe": "ತೀವ್ರ",
}

# Part translations
PART_KN = {
    "leaves": "ಎಲೆಗಳು",
    "stem": "ಕಾಂಡ",
    "bud": "ಮೊಗ್ಗು",
    "tree": "ಮರ",
}

# Healthy practices translations by part
HEALTHY_PRACTICES_BY_PART_KN = {
    "leaves": [
        "ಒಣ ಮತ್ತು ಹಳೆಯ ಎಲೆಗಳನ್ನು ನಿಯಮಿತವಾಗಿ ತೆಗೆದುಹಾಕಿ.",
        "ಉತ್ತಮ ಸೂರ್ಯನ ಬೆಳಕು + ಗಾಳಿ ಪ್ರವಾಹಕ್ಕಾಗಿ ಸರಿಯಾದ ಅಂತರವನ್ನು ಕಾಪಾಡಿಕೊಳ್ಳಿ.",
        "ನಿರಂತರ ಎಲೆ ಒದ್ದೆಯನ್ನು ತಪ್ಪಿಸಿ (ಮೇಲ್ಭಾಗದ ನೀರಾವರಿಯನ್ನು ಕಡಿಮೆ ಮಾಡಿ).",
        "ವಾರಕ್ಕೊಮ್ಮೆ ಕೀಟಗಳಿಗಾಗಿ ಎಲೆಗಳ ಕೆಳಗಿನ ಭಾಗವನ್ನು ಪರಿಶೀಲಿಸಿ.",
        "ಶುದ್ಧ ಕತ್ತರಿಸುವ ಸಾಧನಗಳನ್ನು ಬಳಸಿ ಮತ್ತು ಸೋಂಕಿತ ಎಲೆಗಳನ್ನು ನಾಶಪಡಿಸಿ.",
    ],
    "stem": [
        "ಕಾಂಡದ ಮೇಲೆ ಗಾಯಗಳು/ಕತ್ತರಿಸುವಿಕೆಯನ್ನು ತಪ್ಪಿಸಿ (ಶಿಲೀಂಧ್ರ ಪ್ರವೇಶವನ್ನು ತಡೆಯುತ್ತದೆ).",
        "ಕಾಂಡದ ತಳವನ್ನು ಸ್ವಚ್ಛವಾಗಿ ಇರಿಸಿ (ಕಳೆಗಳು, ಅವಶೇಷಗಳನ್ನು ತೆಗೆದುಹಾಕಿ).",
        "ಕಾಂಡದ ಬಳಿ ಮಣ್ಣಿನ ಒಳಚರಂಡಿಯನ್ನು ಖಚಿತಪಡಿಸಿಕೊಳ್ಳಿ (ನೀರು ನಿಂತಿರಬಾರದು).",
        "ಬಿರುಕುಗಳು/ರಕ್ತಸ್ರಾವ/ಅಂಟು ಸೋರುವಿಕೆಗಾಗಿ ನಿಯಮಿತ ತಪಾಸಣೆ ಮಾಡಿ.",
        "ಸ್ಥಳೀಯ ಕೃಷಿ ಅಧಿಕಾರಿಯ ಶಿಫಾರಸು ಪ್ರಕಾರ ಕಾಂಡದ ತಳಕ್ಕೆ ಸುಣ್ಣದ ಪೇಸ್ಟ್ ಹಚ್ಚಿ.",
    ],
    "bud": [
        "ಕಿರೀಟವನ್ನು ಸ್ವಚ್ಛವಾಗಿ ಇರಿಸಿ (ಸತ್ತ ಕಿರೀಟ ಅವಶೇಷಗಳನ್ನು ತೆಗೆದುಹಾಕಿ).",
        "ಕಿರೀಟ ಪ್ರದೇಶದಲ್ಲಿ ನೀರು ನಿಂತಿರುವುದನ್ನು ತಪ್ಪಿಸಿ.",
        "ಅಂತರ್ಸಂಸ್ಕೃತಿ ಕಾರ್ಯಾಚರಣೆಗಳ ಸಮಯದಲ್ಲಿ ಚಿಗುರು ಎಲೆಯನ್ನು ಗಾಯಗೊಳಿಸಬೇಡಿ.",
        "ಮೃದುತ್ವ, ಕೆಟ್ಟ ವಾಸನೆ ಅಥವಾ ಜೋಲುವಿಕೆಗಾಗಿ ಚಿಗುರು ಎಲೆಯನ್ನು ಪರಿಶೀಲಿಸಿ.",
        "ಕಿರೀಟ ಬೆಳವಣಿಗೆಯನ್ನು ಬಲಪಡಿಸಲು ಸರಿಯಾದ ಪೋಷಣೆಯನ್ನು ಕಾಪಾಡಿಕೊಳ್ಳಿ.",
    ],
    "tree": [
        "ಸರಿಯಾದ ಒಳಚರಂಡಿಯನ್ನು ಕಾಪಾಡಿಕೊಳ್ಳಿ (ನೀರು ನಿಂತಿರುವುದನ್ನು ತಪ್ಪಿಸಿ).",
        "ತೋಟವನ್ನು ಸ್ವಚ್ಛವಾಗಿ ಇರಿಸಿ ಮತ್ತು ಸತ್ತ ಅಂಗಾಂಶವನ್ನು ತೆಗೆದುಹಾಕಿ.",
        "ಸಮತೋಲಿತ ನೀರಾವರಿಯನ್ನು ಖಚಿತಪಡಿಸಿಕೊಳ್ಳಿ ಮತ್ತು ಅತಿಯಾದ ನೀರಾವರಿಯನ್ನು ತಪ್ಪಿಸಿ.",
        "ಆರಂಭಿಕ ರೋಗಲಕ್ಷಣಗಳಿಗಾಗಿ ಪ್ರತಿ 7-10 ದಿನಗಳಿಗೊಮ್ಮೆ ಮೇಲ್ವಿಚಾರಣೆ ಮಾಡಿ.",
    ]
}

# Disease database with Kannada translations
DISEASE_DB_KN: Dict[str, Dict[str, Any]] = {
    # 1) Bud Rot
    "bud_rot": {
        "name": "ಮೊಗ್ಗು ಕೊಳೆತ",
        "part": "ಮೊಗ್ಗು",
        "fertilizers": {
            "mild": [
                {"name": "ಕಾಪರ್ ಆಕ್ಸಿಕ್ಲೋರೈಡ್", "dose": "3 ಗ್ರಾಂ/ಲೀ", "apply": "ಕಿರೀಟಕ್ಕೆ ಸುರಿಯಿರಿ (200-300 ಮಿಲೀ)"},
            ],
            "medium": [
                {"name": "ಕಾಪರ್ ಆಕ್ಸಿಕ್ಲೋರೈಡ್", "dose": "3 ಗ್ರಾಂ/ಲೀ", "apply": "ಕಿರೀಟಕ್ಕೆ ಸುರಿಯಿರಿ (300-500 ಮಿಲೀ)"},
                {"name": "ಕಾರ್ಬೆಂಡಾಜಿಮ್", "dose": "1 ಗ್ರಾಂ/ಲೀ", "apply": "ಪರ್ಯಾಯ ವಾರಾಂತ್ಯ (ಕಿರೀಟ ಸುರಿಯುವಿಕೆ)"},
            ],
            "severe": [
                {"name": "ಕಾಪರ್ ಆಕ್ಸಿಕ್ಲೋರೈಡ್", "dose": "3 ಗ್ರಾಂ/ಲೀ", "apply": "ಹತ್ತಿರದ ಮರಗಳಿಗೆ ತಡೆಗಟ್ಟುವ ಚಿಕಿತ್ಸೆ"},
                {"name": "ಬೋರ್ಡೋ ಮಿಶ್ರಣ", "dose": "1%", "apply": "ಮಳೆಗಾಲದಲ್ಲಿ ಕಿರೀಟ ಚಿಕಿತ್ಸೆ"},
            ],
        },
        "practices": {
            "mild": [
                "ಕಿರೀಟವನ್ನು ಸ್ವಚ್ಛವಾಗಿ ಮಾಡಿ ಮತ್ತು ಸ್ವಲ್ಪ ಸೋಂಕಿತ ಅಂಗಾಂಶವನ್ನು ತೆಗೆದುಹಾಕಿ.",
                "ಒಳಚರಂಡಿಯನ್ನು ಸುಧಾರಿಸಿ ಮತ್ತು ಕಿರೀಟದಲ್ಲಿ ನೀರು ನಿಂತಿರುವುದನ್ನು ತಪ್ಪಿಸಿ.",
            ],
            "medium": [
                "ಸೋಂಕಿತ ಚಿಗುರು ಎಲೆ ಮತ್ತು ಕೊಳೆತ ಕಿರೀಟ ಅಂಗಾಂಶವನ್ನು ಎಚ್ಚರಿಕೆಯಿಂದ ತೆಗೆದುಹಾಕಿ.",
                "ಕಿರೀಟ ಚಿಕಿತ್ಸೆಯನ್ನು ಪ್ರತಿ 7 ದಿನಗಳಿಗೊಮ್ಮೆ ಪುನರಾವರ್ತಿಸಿ (3 ಸುತ್ತುಗಳು).",
                "ಸೋಂಕಿತ ಭಾಗಗಳನ್ನು ಕತ್ತರಿಸಿದ ನಂತರ ಸಾಧನಗಳನ್ನು ಸೋಂಕುರಹಿತಗೊಳಿಸಿ.",
            ],
            "severe": [
                "ಬೆಳೆಯುವ ಬಿಂದು ಸತ್ತಿದ್ದರೆ, ಚೇತರಿಕೆ ಅವಕಾಶ ಕಡಿಮೆ.",
                "ಹರಡುವಿಕೆಯನ್ನು ತಡೆಯಲು ತೀವ್ರವಾಗಿ ಪ್ರಭಾವಿತ ತಾಳೆ ಮರಗಳನ್ನು ತೆಗೆದುಹಾಕಿ.",
                "ಹತ್ತಿರದ ತಾಳೆ ಮರಗಳಿಗೆ ತಡೆಗಟ್ಟುವ ತಾಮ್ರದ ಚಿಕಿತ್ಸೆ ನೀಡಿ.",
            ],
        },
    },

    # 2) Bud Rot Dropping
    "bud_rot_dropping": {
        "name": "ಮೊಗ್ಗು ಕೊಳೆತ ಉದುರುವಿಕೆ",
        "part": "ಮೊಗ್ಗು",
        "fertilizers": {
            "mild": [
                {"name": "ಕಾಪರ್ ಆಕ್ಸಿಕ್ಲೋರೈಡ್", "dose": "3 ಗ್ರಾಂ/ಲೀ", "apply": "ಕಿರೀಟಕ್ಕೆ ಸುರಿಯಿರಿ (200-300 ಮಿಲೀ)"},
            ],
            "medium": [
                {"name": "ಕಾಪರ್ ಆಕ್ಸಿಕ್ಲೋರೈಡ್", "dose": "3 ಗ್ರಾಂ/ಲೀ", "apply": "ವಾರ 1 ಕಿರೀಟ ಸುರಿಯುವಿಕೆ"},
                {"name": "ಕಾರ್ಬೆಂಡಾಜಿಮ್", "dose": "1 ಗ್ರಾಂ/ಲೀ", "apply": "ವಾರ 2 ಕಿರೀಟ ಸುರಿಯುವಿಕೆ (ಪರ್ಯಾಯ)"},
            ],
            "severe": [
                {"name": "ಕಾಪರ್ ಆಕ್ಸಿಕ್ಲೋರೈಡ್", "dose": "3 ಗ್ರಾಂ/ಲೀ", "apply": "ಹತ್ತಿರದ ತಾಳೆ ಮರಗಳಿಗೆ ತಡೆಗಟ್ಟುವ ಕಿರೀಟ ಸುರಿಯುವಿಕೆ"},
            ],
        },
        "practices": {
            "mild": [
                "ಜೋಲುವಿಕೆ ಮತ್ತು ಕೊಳೆತ ವಾಸನೆಗಾಗಿ ಚಿಗುರು ಎಲೆಯನ್ನು ಪರಿಶೀಲಿಸಿ.",
                "ಕಿರೀಟಕ್ಕೆ ಮೇಲ್ಭಾಗದ ನೀರಾವರಿಯನ್ನು ತಪ್ಪಿಸಿ.",
            ],
            "medium": [
                "ಸೋಂಕಿತ ಕಿರೀಟ ಅಂಗಾಂಶಗಳನ್ನು ತೆಗೆದುಹಾಕಿ.",
                "3-4 ವಾರಗಳವರೆಗೆ ವಾರಾಂತ್ಯ ಪರ್ಯಾಯ ಶಿಲೀಂಧ್ರನಾಶಕ ಕಿರೀಟ ಸುರಿಯುವಿಕೆ.",
            ],
            "severe": [
                "ಕಿರೀಟ ಸಂಪೂರ್ಣವಾಗಿ ಕುಸಿದರೆ, ಮರ ಸಾಯಬಹುದು.",
                "ಸತ್ತ ಮರಗಳನ್ನು ತೆಗೆದುಹಾಕಿ ಮತ್ತು ಸುತ್ತಮುತ್ತಲಿನ ಮರಗಳನ್ನು ರಕ್ಷಿಸಿ.",
            ],
        },
    },

    # 3) Grey Leaf Rot
    "leaves_grey_leaf_rot": {
        "name": "ಬೂದು ಎಲೆ ಕೊಳೆತ",
        "part": "ಎಲೆಗಳು",
        "fertilizers": {
            "mild": [
                {"name": "ಮ್ಯಾಂಕೋಜೆಬ್", "dose": "2 ಗ್ರಾಂ/ಲೀ", "apply": "ಎಲೆಗಳ ಎರಡೂ ಬದಿಗಳಲ್ಲಿ ಸಿಂಪಡಿಸಿ"},
            ],
            "medium": [
                {"name": "ಮ್ಯಾಂಕೋಜೆಬ್", "dose": "2 ಗ್ರಾಂ/ಲೀ", "apply": "ವಾರಾಂತ್ಯ ಸಿಂಪಡಿಸಿ (2-3 ಸುತ್ತುಗಳು)"},
                {"name": "ಕಾಪರ್ ಆಕ್ಸಿಕ್ಲೋರೈಡ್", "dose": "3 ಗ್ರಾಂ/ಲೀ", "apply": "ಪರ್ಯಾಯ ಸಿಂಪಡಣೆ ಐಚ್ಛಿಕ"},
            ],
            "severe": [
                {"name": "ಮ್ಯಾಂಕೋಜೆಬ್", "dose": "2 ಗ್ರಾಂ/ಲೀ", "apply": "ವಾರಾಂತ್ಯ ಸಿಂಪಡಿಸಿ (3-4 ಸುತ್ತುಗಳು)"},
                {"name": "ಕಾಪರ್ ಆಕ್ಸಿಕ್ಲೋರೈಡ್", "dose": "3 ಗ್ರಾಂ/ಲೀ", "apply": "ಹರಡುತ್ತಿದ್ದರೆ ಪರ್ಯಾಯ"},
            ],
        },
        "practices": {
            "mild": [
                "ಸಣ್ಣ ಸೋಂಕಿತ ಎಲೆ ಭಾಗಗಳನ್ನು ತೆಗೆದುಹಾಕಿ.",
                "ದೀರ್ಘ ಅವಧಿಯ ಎಲೆ ಒದ್ದೆಯನ್ನು ತಪ್ಪಿಸಿ.",
            ],
            "medium": [
                "ಹೆಚ್ಚು ಸೋಂಕಿತ ಎಲೆಗಳನ್ನು ತೆಗೆದುಹಾಕಿ ಮತ್ತು ನಾಶಪಡಿಸಿ.",
                "ಸೂರ್ಯನ ಬೆಳಕಿನ ಪ್ರವೇಶ ಮತ್ತು ಗಾಳಿ ಪ್ರವಾಹವನ್ನು ಸುಧಾರಿಸಿ.",
            ],
            "severe": [
                "ಹರಡುವಿಕೆಯನ್ನು ಕಡಿಮೆ ಮಾಡಲು ಅನೇಕ ಸೋಂಕಿತ ಎಲೆಗಳನ್ನು ತೆಗೆದುಹಾಕಿ.",
                "ನಿಯಂತ್ರಣವಾಗುವವರೆಗೆ ಶಿಲೀಂಧ್ರನಾಶಕ ವೇಳಾಪಟ್ಟಿಯನ್ನು ಮುಂದುವರಿಸಿ.",
            ],
        },
    },

    # 4) Leaf Rot
    "leaf_rot": {
        "name": "ಎಲೆ ಕೊಳೆತ",
        "part": "ಎಲೆಗಳು",
        "fertilizers": {
            "mild": [
                {"name": "ಕಾಪರ್ ಆಕ್ಸಿಕ್ಲೋರೈಡ್", "dose": "3 ಗ್ರಾಂ/ಲೀ", "apply": "ಎಲೆ ಸಿಂಪಡಣೆ"},
            ],
            "medium": [
                {"name": "ಕಾಪರ್ ಆಕ್ಸಿಕ್ಲೋರೈಡ್", "dose": "3 ಗ್ರಾಂ/ಲೀ", "apply": "ವಾರಾಂತ್ಯ ಸಿಂಪಡಿಸಿ"},
                {"name": "ಮ್ಯಾಂಕೋಜೆಬ್", "dose": "2 ಗ್ರಾಂ/ಲೀ", "apply": "ಪರ್ಯಾಯ ಐಚ್ಛಿಕ"},
            ],
            "severe": [
                {"name": "ಕಾಪರ್ ಆಕ್ಸಿಕ್ಲೋರೈಡ್", "dose": "3 ಗ್ರಾಂ/ಲೀ", "apply": "ವಾರಾಂತ್ಯ ಸಿಂಪಡಿಸಿ (3-4 ಸುತ್ತುಗಳು)"},
            ],
        },
        "practices": {
            "mild": [
                "ಆರಂಭಿಕ ಕೊಳೆಯುತ್ತಿರುವ ಎಲೆ ಭಾಗಗಳನ್ನು ತೆಗೆದುಹಾಕಿ.",
                "ಅತಿಯಾದ ನೀರಾವರಿಯನ್ನು ತಪ್ಪಿಸಿ ಮತ್ತು ಒಳಚರಂಡಿಯನ್ನು ಸುಧಾರಿಸಿ.",
            ],
            "medium": [
                "ಸೋಂಕಿತ ಎಲೆಗಳನ್ನು ಸಂಪೂರ್ಣವಾಗಿ ತೆಗೆದುಹಾಕಿ.",
                "ದಟ್ಟವಾದ ಎಲೆಗಳನ್ನು ಕತ್ತರಿಸುವ ಮೂಲಕ ಗಾಳಿ ಪ್ರವಾಹವನ್ನು ಸುಧಾರಿಸಿ.",
            ],
            "severe": [
                "ತೀವ್ರವಾಗಿ ಸೋಂಕಿತ ಎಲೆ ವಸ್ತುವನ್ನು ನಾಶಪಡಿಸಿ.",
                "ಸಾಧನಗಳನ್ನು ಸ್ವಚ್ಛಗೊಳಿಸುವ ಮೂಲಕ ಬೀಜಕಗಳ ಹರಡುವಿಕೆಯನ್ನು ತಪ್ಪಿಸಿ.",
            ],
        },
    },

    # 5) Stem Bleeding
    "stem_bleeding": {
        "name": "ಕಾಂಡ ರಕ್ತಸ್ರಾವ",
        "part": "ಕಾಂಡ",
        "fertilizers": {
            "mild": [
                {"name": "ಕಾಪರ್ ಆಕ್ಸಿಕ್ಲೋರೈಡ್ ಪೇಸ್ಟ್", "dose": "ಪೇಸ್ಟ್", "apply": "ಸೋಂಕಿತ ಪ್ರದೇಶಕ್ಕೆ ಹಚ್ಚಿ"},
            ],
            "medium": [
                {"name": "ಕಾಪರ್ ಆಕ್ಸಿಕ್ಲೋರೈಡ್ ಪೇಸ್ಟ್", "dose": "ಪೇಸ್ಟ್", "apply": "ಪ್ರತಿ 15 ದಿನಗಳಿಗೊಮ್ಮೆ ಹಚ್ಚಿ"},
                {"name": "ಟ್ರೈಡೆಮಾರ್ಫ್", "dose": "5%", "apply": "ಗಾಯದ ಪ್ರದೇಶಕ್ಕೆ ಹಚ್ಚಿ"},
            ],
            "severe": [
                {"name": "ಕಾಪರ್ ಆಕ್ಸಿಕ್ಲೋರೈಡ್ ಪೇಸ್ಟ್", "dose": "ಪೇಸ್ಟ್", "apply": "ನಿಯಮಿತ ಅನ್ವಯ"},
                {"name": "ಟ್ರೈಡೆಮಾರ್ಫ್", "dose": "5%", "apply": "ರಕ್ತಸ್ರಾವ ನಿಲ್ಲುವವರೆಗೆ ಪರ್ಯಾಯ"},
            ],
        },
        "practices": {
            "mild": [
                "ರಕ್ತಸ್ರಾವವಾಗುತ್ತಿರುವ ಪ್ರದೇಶವನ್ನು ಸ್ವಚ್ಛಗೊಳಿಸಿ.",
                "ಕಾಂಡದ ತಳದ ಬಳಿ ಒಳಚರಂಡಿಯನ್ನು ಖಚಿತಪಡಿಸಿಕೊಳ್ಳಿ.",
            ],
            "medium": [
                "ಸೋಂಕಿತ ಅಂಗಾಂಶವನ್ನು ಹೊರಗೆ ತೆಗೆದುಹಾಕಿ.",
                "ಪ್ರತಿ 15 ದಿನಗಳಿಗೊಮ್ಮೆ ಶಿಲೀಂಧ್ರನಾಶಕ ಪೇಸ್ಟ್ ಹಚ್ಚಿ.",
            ],
            "severe": [
                "ಸುತ್ತಮುತ್ತಲಿನ ಸೋಂಕಿತ ಅಂಗಾಂಶವನ್ನು ತೆಗೆದುಹಾಕಿ.",
                "ವ್ಯವಸ್ಥಿತ ಶಿಲೀಂಧ್ರನಾಶಕ ಇಂಜೆಕ್ಷನ್ ಬಳಸಿ.",
                "ಹತ್ತಿರದ ತಾಳೆ ಮರಗಳನ್ನು ಸೋಂಕಿಗೆ ಪರಿಶೀಲಿಸಿ.",
            ],
        },
    },

    # 6) Whitefly
    "whitefly": {
        "name": "ಬಿಳಿ ನೊಣ",
        "part": "ಎಲೆಗಳು",
        "fertilizers": {
            "mild": [
                {"name": "ಬೇವಿನ ಎಣ್ಣೆ", "dose": "2%", "apply": "ಎಲೆಗಳ ಕೆಳಗಿನ ಭಾಗದಲ್ಲಿ ಸಿಂಪಡಿಸಿ"},
            ],
            "medium": [
                {"name": "ಬೇವಿನ ಎಣ್ಣೆ", "dose": "2%", "apply": "ವಾರಾಂತ್ಯ ಸಿಂಪಡಿಸಿ"},
                {"name": "ಕೀಟನಾಶಕ ಸಾಬೂನು", "dose": "1%", "apply": "ಪರ್ಯಾಯ ಸಿಂಪಡಣೆ"},
            ],
            "severe": [
                {"name": "ಇಮಿಡಾಕ್ಲೋಪ್ರಿಡ್", "dose": "0.3 ಮಿಲೀ/ಲೀ", "apply": "ವ್ಯವಸ್ಥಿತ ಸಿಂಪಡಣೆ"},
                {"name": "ಬೇವಿನ ಎಣ್ಣೆ", "dose": "2%", "apply": "ನಿಯಂತ್ರಣದ ನಂತರ ಅನುಸರಣೆ"},
            ],
        },
        "practices": {
            "mild": [
                "ಹಳದಿ ಅಂಟು ಬಲೆಗಳನ್ನು ಇರಿಸಿ.",
                "ಎಲೆಗಳ ಕೆಳಗಿನ ಭಾಗವನ್ನು ನಿಯಮಿತವಾಗಿ ಪರಿಶೀಲಿಸಿ.",
            ],
            "medium": [
                "ಅತಿಯಾದ ಸೋಂಕಿತ ಎಲೆಗಳನ್ನು ತೆಗೆದುಹಾಕಿ.",
                "ಕಳೆಗಳನ್ನು ನಿಯಂತ್ರಿಸಿ.",
            ],
            "severe": [
                "ಹಲವಾರು ಸಿಂಪಡಣೆಗಳೊಂದಿಗೆ ಸಮಗ್ರ ಕೀಟ ನಿರ್ವಹಣೆ ಬಳಸಿ.",
                "ನೈಸರ್ಗಿಕ ಪರಭಕ್ಷಕಗಳನ್ನು ಪರಿಚಯಿಸುವುದನ್ನು ಪರಿಗಣಿಸಿ.",
            ],
        },
    },
}


def translate_recommendation(recommendation: Dict[str, Any], lang: str = "en") -> Dict[str, Any]:
    """
    Translate a recommendation response to the specified language.
    
    Args:
        recommendation: Original recommendation dict
        lang: Language code ('en' or 'kn')
    
    Returns:
        Translated recommendation dict
    """
    if lang == "en":
        return recommendation
    
    if lang != "kn":
        return recommendation  # Unsupported language, return original
    
    translated = recommendation.copy()
    
    # Translate disease name
    disease_en = recommendation.get("disease", "")
    translated["disease"] = DISEASE_NAMES_KN.get(disease_en, disease_en)
    
    # Translate status
    status_en = recommendation.get("status", "")
    translated["status"] = STATUS_KN.get(status_en, status_en)
    
    # Translate severity
    severity_en = recommendation.get("severity", "")
    if severity_en:
        translated["severity"] = SEVERITY_KN.get(severity_en, severity_en)
    
    # Translate part
    part_en = recommendation.get("part", "")
    translated["part"] = PART_KN.get(part_en, part_en)
    
    # Translate fertilizers and practices from Kannada DB
    label_key = _get_label_key_from_disease(disease_en)
    if label_key and label_key in DISEASE_DB_KN:
        kn_data = DISEASE_DB_KN[label_key]
        severity = recommendation.get("severity", "")
        
        # If severity is present, get that specific level
        if severity and severity in kn_data.get("fertilizers", {}):
            translated["fertilizers"] = kn_data["fertilizers"][severity]
            translated["practices"] = kn_data["practices"][severity]
        else:
            # No severity (simple recommendation) - combine all levels
            all_fertilizers = []
            all_practices = []
            for sev in ["mild", "medium", "severe"]:
                if sev in kn_data.get("fertilizers", {}):
                    all_fertilizers.extend(kn_data["fertilizers"][sev])
                if sev in kn_data.get("practices", {}):
                    all_practices.extend(kn_data["practices"][sev])
            
            # Deduplicate
            seen_fert = set()
            unique_fertilizers = []
            for fert in all_fertilizers:
                fert_key = fert["name"]
                if fert_key not in seen_fert:
                    seen_fert.add(fert_key)
                    unique_fertilizers.append(fert)
            
            seen_prac = set()
            unique_practices = []
            for prac in all_practices:
                if prac not in seen_prac:
                    seen_prac.add(prac)
                    unique_practices.append(prac)
            
            translated["fertilizers"] = unique_fertilizers
            translated["practices"] = unique_practices
            
    elif "healthy" in disease_en.lower() or recommendation.get("status") == "healthy":
        part_norm = _normalize_part_for_kn(part_en)
        if part_norm in HEALTHY_PRACTICES_BY_PART_KN:
            translated["practices"] = HEALTHY_PRACTICES_BY_PART_KN[part_norm]
    
    return translated


def _get_label_key_from_disease(disease_name: str) -> str:
    """Get the database key from disease name."""
    disease_to_key = {
        "Bud Rot": "bud_rot",
        "Bud Rot Dropping": "bud_rot_dropping",
        "Grey Leaf Rot": "leaves_grey_leaf_rot",
        "Leaf Rot": "leaf_rot",
        "Stem Bleeding": "stem_bleeding",
        "Whitefly": "whitefly",
    }
    return disease_to_key.get(disease_name, "")


def _normalize_part_for_kn(part: str) -> str:
    """Normalize part name for lookup."""
    part_map = {
        "leaves": "leaves",
        "ಎಲೆಗಳು": "leaves",
        "stem": "stem",
        "ಕಾಂಡ": "stem",
        "bud": "bud",
        "ಮೊಗ್ಗು": "bud",
        "tree": "tree",
        "ಮರ": "tree",
    }
    return part_map.get(part, "tree")


def translate_video_recommendations(video_recs: Dict[str, Any], lang: str = "en") -> Dict[str, Any]:
    """
    Translate full video recommendations (stem, leaves, bud) to specified language.
    
    Args:
        video_recs: Video recommendations dict containing stem, leaves, bud sections
        lang: Language code ('en' or 'kn')
    
    Returns:
        Translated video recommendations
    """
    if lang == "en":
        return video_recs
    
    translated = {}
    for part in ["stem", "leaves", "bud"]:
        if part in video_recs:
            part_data = video_recs[part].copy()
            if "recommendation" in part_data:
                part_data["recommendation"] = translate_recommendation(
                    part_data["recommendation"], lang
                )
            translated[part] = part_data
    
    return translated

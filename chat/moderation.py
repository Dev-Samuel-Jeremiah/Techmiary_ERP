# chat/moderation.py
"""
Content moderation for the chat system.
Uses pattern matching to detect abusive, sexual, and inappropriate content.
Logs all violations to BlockedMessage for admin review.
"""

import re

# ── Category definitions ──────────────────────────────────────────────────────
# Each entry: (pattern_list, category_label, user_reason)

RULES = [
    # Sexual / explicit content
    {
        'category': 'sexual',
        'label': 'Sexual / Explicit Content',
        'reason': 'Your message contains sexually explicit language or content. '
                  'This platform is a school environment — such content is strictly prohibited.',
        'patterns': [
            r'\bsex\b', r'\bporn\b', r'\bnude\b', r'\bnaked\b', r'\bboobs?\b',
            r'\bdick\b', r'\bpenis\b', r'\bvagina\b', r'\bpussy\b', r'\bcunt\b',
            r'\brass\b', r'\bbutt\b', r'\bfuck(ing)?\b', r'\bfucker\b',
            r'\bhorny\b', r'\bsexual\b', r'\blust\b', r'\bseduce\b',
            r'\berotic\b', r'\bintercourse\b', r'\bmasturbat\w*\b',
            r'\borgasm\b', r'\bnipple\b', r'\bbreasts?\b', r'\bgenitals?\b',
            r'\bslut\b', r'\bwhore\b', r'\bprostitut\w*\b', r'\bstrip(per)?\b',
        ],
    },

    # Hate speech / racial slurs
    {
        'category': 'hate_speech',
        'label': 'Hate Speech / Discrimination',
        'reason': 'Your message contains hate speech, slurs, or discriminatory language. '
                  'All students and staff deserve a respectful environment.',
        'patterns': [
            r'\brigger\b', r'\bfaggot\b', r'\bretard\b', r'\bspastic\b',
            r'\bkike\b', r'\bwetback\b', r'\bspic\b', r'\bgook\b',
            r'\bchink\b', r'\bcoon\b', r'\bpaki\b', r'\btranny\b',
            r'\bheeb\b', r'\bdyke\b', r'\bbitch\b', r'\bmoron\b',
        ],
    },

    # Threats / violence
    {
        'category': 'threat',
        'label': 'Threats / Violence',
        'reason': 'Your message contains threatening or violent language. '
                  'Threats of any kind are unacceptable and may be reported to school authorities.',
        'patterns': [
            r'\bi.ll kill\b', r'\bi will kill\b', r'\bkill you\b',
            r'\bi.ll hurt\b', r'\bi will hurt\b', r'\bbeat you up\b',
            r'\bi.ll stab\b', r'\bstab you\b', r'\bbomb\b',
            r'\bshoot you\b', r'\bi.ll shoot\b', r'\bgonna kill\b',
            r'\bwanna kill\b', r'\bdead meat\b', r'\byou.re dead\b',
            r'\bmurder\b', r'\bdie bitch\b', r'\bgo die\b',
        ],
    },

    # Bullying / harassment / insults
    {
        'category': 'bullying',
        'label': 'Bullying / Harassment',
        'reason': 'Your message contains bullying, harassing, or insulting language. '
                  'Respect for all members of this school community is required.',
        'patterns': [
            # Direct insults
            r'\bstupid\b', r'\bidiot\b', r'\bmoron\b', r'\bimbecile\b',
            r'\bdumb(ass)?\b', r'\bbrainless\b', r'\bdunce\b', r'\bfool\b',
            r'\bimbecile\b', r'\bnitwit\b', r'\bnumskull\b', r'\bdimwit\b',
            r'\bloser\b', r'\bweirdo\b', r'\bfreak\b', r'\bwaste(r)?\b',
            r'\buseless\b', r'\bpathetic\b', r'\bpitiful\b', r'\bworthless\b',
            r'\bdisgusting\b', r'\bgross\b', r'\brepulsive\b',
            # Appearance insults
            r'\byou.?re\s+ugly\b', r'\bso\s+ugly\b', r'\bfat\s+(pig|cow|ass)\b',
            r'\byou.?re\s+fat\b', r'\bobese\b',
            # Social isolation
            r'\bno\s+one\s+likes\s+you\b', r'\beveryone\s+hates\s+you\b',
            r'\byou\s+have\s+no\s+friends\b', r'\bgo\s+away\b',
            r'\bnobody\s+wants\s+you\b',
            # Self-harm encouragement
            r'\bkill\s+your\s*self\b', r'\bkys\b', r'\bgo\s+hang\s+yourself\b',
            r'\bkill\s+ur\s*self\b', r'\bgo\s+die\b',
            # Hate
            r'\bi\s+hate\s+you\b', r'\byou\s+suck\b', r'\byou\s+stink\b',
        ],
    },

    # Self-harm / suicide
    {
        'category': 'self_harm',
        'label': 'Self-Harm / Suicide Content',
        'reason': 'Your message contains references to self-harm or suicide. '
                  'If you or someone you know needs help, please speak to a school counsellor immediately.',
        'patterns': [
            r'\bcut myself\b', r'\bcutting myself\b', r'\bwant to die\b',
            r'\bwanna die\b', r'\bend my life\b', r'\bsuicide\b',
            r'\bsuicidal\b', r'\bkill myself\b', r'\bkilling myself\b',
            r'\boverdose\b', r'\bself.harm\b', r'\bself harm\b',
        ],
    },
]


def _compile_rules():
    compiled = []
    for rule in RULES:
        compiled.append({
            **rule,
            'compiled': [re.compile(p, re.IGNORECASE) for p in rule['patterns']],
        })
    return compiled


_COMPILED_RULES = _compile_rules()


def check_message(content: str) -> dict:
    """
    Check a message for policy violations.

    Returns:
        {
            'allowed': True/False,
            'category': 'sexual' | 'hate_speech' | 'threat' | 'bullying' | 'self_harm' | None,
            'label': Human-readable category name,
            'reason': Explanation shown to the user,
            'matched_pattern': The regex that matched (for logging),
        }
    """
    for rule in _COMPILED_RULES:
        for pattern in rule['compiled']:
            match = pattern.search(content)
            if match:
                return {
                    'allowed': False,
                    'category': rule['category'],
                    'label': rule['label'],
                    'reason': rule['reason'],
                    'matched_pattern': pattern.pattern,
                    'matched_word': match.group(0),
                }
    return {
        'allowed': True,
        'category': None,
        'label': None,
        'reason': None,
        'matched_pattern': None,
        'matched_word': None,
    }
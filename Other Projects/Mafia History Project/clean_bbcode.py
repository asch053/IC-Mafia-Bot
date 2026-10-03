# clean_bbcode.py
"""
Utility module to clean forum BBCode, HTML entities, and formatting artifacts.
Optimizes historic post content for LLM ingestion and token efficiency.
"""

import re
import html

def clean_forum_text(raw_text: str) -> str:
    """
    Cleans raw forum post text by stripping BBCode tags, unescaping HTML,
    normalizing whitespace, and removing forum signature footers.
    """
    if not raw_text:
        return ""

    # 1. Unescape HTML entities (&quot;, &#039;, &amp;, etc.)
    text = html.unescape(raw_text)

    # 2. Extract quote author/attribution before removing quotes if needed
    # Replace [quote=Author]...[/quote] with "[Quote from Author]: ..."
    text = re.sub(r'\[quote=([^\]]+)\]', r'[Quote from \1]: ', text, flags=re.IGNORECASE)
    text = re.sub(r'\[quote\]', '[Quote]: ', text, flags=re.IGNORECASE)
    text = re.sub(r'\[/quote\]', ' [End Quote] ', text, flags=re.IGNORECASE)

    # 3. Strip general BBCode tags like [b], [/b], [i], [/i], [color=...], [url=...], [img]...[/img]
    text = re.sub(r'\[img\][^\[]*\[/img\]', '[Image]', text, flags=re.IGNORECASE)
    text = re.sub(r'\[url=[^\]]*\]([^\[]*)\[/url\]', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\[url\][^\[]*\[/url\]', '[Link]', text, flags=re.IGNORECASE)
    text = re.sub(r'\[/?(?:b|i|u|s|color|size|font|center|list|code|spoiler)[^\]]*\]', '', text, flags=re.IGNORECASE)

    # 4. Strip asterisks repeated as section dividers (e.g. ******************)
    text = re.sub(r'\*{4,}', ' --- ', text)

    # 5. Remove common forum signature footers (e.g. "Insanity and genius are closely related!*** Eltie for mod! ***")
    text = re.sub(r'Insanity and genius are closely related!.*$', '', text, flags=re.IGNORECASE)

    # 6. Normalize excessive spaces, tabs, and newlines
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()

if __name__ == "__main__":
    sample = "Hello [b]World[/b]! [quote=Alice]I suspect Bob![/quote] Visit [url=http://test.com]here[/url] &quot;done&quot;"
    print("Cleaned:", clean_forum_text(sample))

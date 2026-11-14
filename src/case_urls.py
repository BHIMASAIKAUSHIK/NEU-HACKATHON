"""URL constants and builders for the Case Room."""

from urllib.parse import urlencode


API_KEYS_URL = "https://platform.claude.com/settings/keys"
CLAUDE_MESSAGES_URL = "https://api.anthropic.com/v1/messages"


def source_record_url(sample_id, reference):
    query = urlencode({"sample": sample_id, "source": reference})
    return f"?{query}#original-source-record"

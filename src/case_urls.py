"""URL constants and builders for the Case Room."""

from urllib.parse import unquote, urlencode, urlsplit


API_KEYS_URL = "https://platform.claude.com/settings/keys"
CLAUDE_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
XENA_DATASET_PAGE = "https://xenabrowser.net/datapages/"
XENA_TCGA_HUB = "https://tcga.xenahubs.net"


def xena_dataset_page(download_url):
    dataset = unquote(urlsplit(download_url).path).removeprefix("/download/")
    query = urlencode({"dataset": dataset.removesuffix(".gz"), "host": XENA_TCGA_HUB})
    return f"{XENA_DATASET_PAGE}?{query}"


def source_record_url(sample_id, reference):
    query = urlencode({"sample": sample_id, "source": reference})
    return f"?{query}#original-source-record"

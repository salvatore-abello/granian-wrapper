from urllib.parse import parse_qs as urllib_parse_qs

async def parse_qs(query_string: str) -> dict:
    query = urllib_parse_qs(query_string)

    return {k: v[0] if len(v) == 1 else v for k, v in query.items()}

"""프록시 체인을 검증해 요청의 실제 클라이언트 IP를 결정한다."""

from __future__ import annotations

from functools import lru_cache
from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network

from fastapi import Request

from ..database.connection import settings

IPAddress = IPv4Address | IPv6Address


@lru_cache(maxsize=32)
def _trusted_networks(raw_cidrs: str) -> tuple:
    """쉼표로 구분된 CIDR 목록을 파싱한다.

    설정 검증에서도 같은 형식을 확인하지만, 이 함수는 테스트에서 별도 문자열을
    넣을 수 있도록 독립적으로 동작한다.
    """
    networks = []
    for item in raw_cidrs.split(","):
        value = item.strip()
        if value:
            networks.append(ip_network(value, strict=False))
    return tuple(networks)


def _is_trusted(address: IPAddress, raw_cidrs: str) -> bool:
    return any(address in network for network in _trusted_networks(raw_cidrs))


def _parse_forwarded_for(value: str) -> list[IPAddress] | None:
    """X-Forwarded-For를 IP 목록으로 파싱한다. 하나라도 잘못되면 폐기한다."""
    parsed: list[IPAddress] = []
    for item in value.split(","):
        candidate = item.strip()
        if not candidate:
            return None
        try:
            parsed.append(ip_address(candidate))
        except ValueError:
            return None
    return parsed or None


def get_client_ip(request: Request, trusted_proxy_cidrs: str | None = None) -> str:
    """신뢰된 프록시가 전달한 X-Forwarded-For만 사용한다.

    직접 연결한 피어가 신뢰 목록에 없으면 헤더를 전부 무시한다. 신뢰된 프록시가
    여러 단계인 경우 오른쪽에서 왼쪽으로 프록시를 벗겨 첫 비신뢰 주소를 실제
    클라이언트로 본다. 이 방식은 사용자가 헤더 왼쪽에 임의 주소를 추가해도
    신뢰 경계를 넘어설 수 없게 한다.
    """
    peer_text = request.client.host if request.client else "unknown"
    try:
        peer = ip_address(peer_text)
    except ValueError:
        return peer_text

    raw_cidrs = (
        settings.trusted_proxy_cidrs
        if trusted_proxy_cidrs is None
        else trusted_proxy_cidrs
    )
    if not raw_cidrs or not _is_trusted(peer, raw_cidrs):
        return str(peer)

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return str(peer)

    chain = _parse_forwarded_for(forwarded)
    if chain is None:
        return str(peer)

    # 오른쪽 끝은 현재 연결 피어다. 신뢰된 프록시만 제거하고 첫 비신뢰 홉을 반환한다.
    hops = [*chain, peer]
    index = len(hops) - 1
    while index > 0 and _is_trusted(hops[index], raw_cidrs):
        index -= 1
    return str(hops[index])

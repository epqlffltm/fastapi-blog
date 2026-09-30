#app/service/ratelimit.py

'''
2026-07-28
로그인 실패 횟수 제한 (브루트포스 방어)

2026-09-30
한도 확인과 증가를 한 Lua 스크립트로 묶어 동시 요청의 한도 우회(TOCTOU) 차단
'''

import logging

from fastapi import Depends
from redis.asyncio import Redis

from ..database.cache import get_redis_client

logger = logging.getLogger(__name__)


class LoginRateLimitService:
    """로그인 실패를 계정별·IP별로 세어 브루트포스를 막는다.

    두 축을 모두 세는 이유:
      - 계정별만 세면 공격자가 IP 하나로 계정 수천 개를 훑는다 (password spraying).
      - IP별만 세면 봇넷이 IP 를 갈아타며 한 계정을 집중 공략한다.
    한쪽이라도 한도를 넘으면 막는다.
    """

    window: int = 15 * 60      # 실패 집계 구간 (15분)
    max_per_email: int = 5     # 계정별 한도
    max_per_ip: int = 20       # IP별 한도 (공용 IP 뒤 여러 사람을 감안해 넉넉히)

    def __init__(self, redis: Redis = Depends(get_redis_client)):
        self.redis = redis

    @staticmethod
    def _email_key(email: str) -> str:
        return f"login-fail:email:{email.lower()}"

    @staticmethod
    def _ip_key(ip: str) -> str:
        return f"login-fail:ip:{ip}"

    async def acquire_attempt(self, email: str, ip: str) -> bool:
        """시도 한 번을 원자적으로 '예약'한다. 비밀번호 검증 '전에' 부른다.

        예전에는 읽기(is_blocked)와 기록(record_failure)이 따로 있어서,
        bcrypt 가 도는 사이 동시에 들어온 요청 N개가 모두 같은 카운트를 보고
        한도를 통과했다 (TOCTOU). 확인과 증가를 한 Lua 스크립트로 묶으면
        Redis 가 스크립트를 한 번에 하나씩만 실행하므로 한도를 넘을 수 없다.

        bcrypt 는 의도적으로 느리므로, 막을 요청에 해시 계산을 태우면
        그 자체가 CPU 고갈 공격 통로가 된다. 그래서 막히면 증가도 하지 않는다.
        True 면 시도해도 되고, False 면 429 로 거절한다.
        """
        script = """
        -- LOGIN_ATTEMPT_ACQUIRE
        local email_count = tonumber(redis.call("GET", KEYS[1]) or "0")
        local ip_count = tonumber(redis.call("GET", KEYS[2]) or "0")

        if email_count >= tonumber(ARGV[1]) or ip_count >= tonumber(ARGV[2]) then
            return 0
        end

        -- INCR 과 EXPIRE 를 한 스크립트에 둬야 만료 없는 카운터가 남지 않는다
        local window = tonumber(ARGV[3])
        for i = 1, 2 do
            local count = redis.call("INCR", KEYS[i])
            if count == 1 then
                redis.call("EXPIRE", KEYS[i], window)
            end
        end
        return 1
        """
        try:
            result = await self.redis.eval(
                script,
                2,
                self._email_key(email),
                self._ip_key(ip),
                self.max_per_email,
                self.max_per_ip,
                self.window,
            )
        except Exception:
            # Redis 장애 시 fail-open. 레이트리밋은 완화 장치이고 1차 방어는
            # bcrypt 와 비밀번호 길이 제한이다. 캐시가 죽었다고 전 사용자의
            # 로그인을 막는 쪽이 더 큰 사고라 판단했다 (대신 로그는 남긴다)
            logger.exception("login rate limit check failed; allowing attempt")
            return True

        return int(result) == 1

    async def reset(self, email: str, ip: str) -> None:
        """로그인에 성공하면 계정 카운터를 지우고, IP 카운터는 이번 몫만 되돌린다.

        시도는 검증 전에 미리 세므로 성공한 시도도 IP 카운터에 들어가 있다.
        그 1 만 빼고 나머지 실패 기록은 남긴다. 공격자가 자기 계정 하나로
        성공해서 IP 한도를 초기화하는 걸 막기 위해서다.
        """
        script = """
        -- LOGIN_ATTEMPT_RESET
        redis.call("DEL", KEYS[1])
        local ip_count = tonumber(redis.call("GET", KEYS[2]) or "0")
        if ip_count > 0 then
            redis.call("DECR", KEYS[2])
        end
        return 1
        """
        try:
            await self.redis.eval(
                script,
                2,
                self._email_key(email),
                self._ip_key(ip),
            )
        except Exception:
            logger.exception("login failure reset failed")

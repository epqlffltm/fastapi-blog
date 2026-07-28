#app/service/ratelimit.py

'''
2026-07-28
로그인 실패 횟수 제한 (브루트포스 방어)
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

    async def is_blocked(self, email: str, ip: str) -> bool:
        """지금 시도를 받아줄지 판단한다. 비밀번호 검증 '전에' 부른다.

        bcrypt 는 의도적으로 느리므로, 막을 요청에 해시 계산을 태우면
        그 자체가 CPU 고갈 공격 통로가 된다.
        """
        script = """
        local email_count = tonumber(redis.call("GET", KEYS[1]) or "0")
        local ip_count = tonumber(redis.call("GET", KEYS[2]) or "0")

        if email_count >= tonumber(ARGV[1]) or ip_count >= tonumber(ARGV[2]) then
            return 1
        end
        return 0
        """
        try:
            result = await self.redis.eval(
                script,
                2,
                self._email_key(email),
                self._ip_key(ip),
                self.max_per_email,
                self.max_per_ip,
            )
        except Exception:
            # Redis 장애 시 fail-open. 레이트리밋은 완화 장치이고 1차 방어는
            # bcrypt 와 비밀번호 길이 제한이다. 캐시가 죽었다고 전 사용자의
            # 로그인을 막는 쪽이 더 큰 사고라 판단했다 (대신 로그는 남긴다)
            logger.exception("login rate limit check failed; allowing attempt")
            return False

        return result == 1

    async def record_failure(self, email: str, ip: str) -> None:
        """실패를 두 카운터에 기록한다.

        INCR 과 EXPIRE 를 파이썬에서 두 번 호출하면 그 사이에 프로세스가
        죽었을 때 만료 없는 카운터가 영구히 남는다. 한 스크립트로 묶는다.
        """
        script = """
        local window = tonumber(ARGV[1])
        for i = 1, 2 do
            local count = redis.call("INCR", KEYS[i])
            if count == 1 then
                redis.call("EXPIRE", KEYS[i], window)
            end
        end
        return 1
        """
        try:
            await self.redis.eval(
                script,
                2,
                self._email_key(email),
                self._ip_key(ip),
                self.window,
            )
        except Exception:
            logger.exception("login failure record failed")

    async def reset(self, email: str) -> None:
        """로그인에 성공하면 계정 카운터를 지운다.

        IP 카운터는 남긴다. 공격자가 자기 계정 하나로 성공해서
        IP 한도를 초기화하는 걸 막기 위해서다.
        """
        try:
            await self.redis.delete(self._email_key(email))
        except Exception:
            logger.exception("login failure reset failed")
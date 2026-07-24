// 2026-07-24 fetch 공통 (쿠키 인증)

// 모든 요청에 credentials를 붙여야 httpOnly 쿠키가 함께 나간다.
// 한 곳에 모아두면 페이지마다 빠뜨리는 실수가 구조적으로 막힌다.
async function request(path, options = {}) {
    const response = await fetch(path, {
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        ...options,
    });

    if (response.status === 204) return null;

    let data = null;
    try {
        data = await response.json();
    } catch {
        data = null;
    }

    if (!response.ok) {
        throw new ApiError(response.status, extractMessage(data, response.status));
    }
    return data;
}

class ApiError extends Error {
    constructor(status, message) {
        super(message);
        this.status = status;
    }
}

// FastAPI의 detail은 문자열이거나 검증 오류 배열이다
function extractMessage(data, status) {
    if (!data || !data.detail) return `요청 실패 (${status})`;
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
        return data.detail.map((e) => e.msg).join(", ");
    }
    return `요청 실패 (${status})`;
}

const api = {
    get: (path) => request(path),
    post: (path, body) =>
        request(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
    patch: (path, body) =>
        request(path, { method: "PATCH", body: JSON.stringify(body ?? {}) }),
    del: (path) => request(path, { method: "DELETE" }),
};
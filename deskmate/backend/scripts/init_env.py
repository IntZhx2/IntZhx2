"""首次创建仅本机可读的环境文件，不打印凭据且不覆盖已有配置。"""

import os
import secrets
from pathlib import Path


def main() -> None:
    target = Path(__file__).resolve().parents[1] / ".env"
    template = target.with_name(".env.example").read_text(encoding="utf-8")
    values = {
        key: secrets.token_urlsafe(32)
        for key in ("JWT_SECRET", "EDGE_TOKEN", "ADMIN_PASSWORD", "DEMO_PASSWORD")
    }
    lines = []
    for line in template.splitlines():
        key = line.split("=", 1)[0]
        lines.append(f"{key}={values[key]}" if key in values else line)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print("已创建 backend/.env（权限 0600）。账号 admin/demo 的密码请在本地文件中查看。")


if __name__ == "__main__":
    main()

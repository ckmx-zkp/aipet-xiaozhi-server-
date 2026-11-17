"""生成隔离候选上下文，保留线上文件中的既有差异；不读取凭据。"""
import io
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAGE = Path(__file__).resolve().parent
SOURCE = ROOT / "xiaozhi-esp32-server/main/xiaozhi-server"
BASE = "74cf3fdfeb101c1d6025e8acd0352af928a0141c"
FILES = ["core/http_server.py", "core/handle/helloHandle.py", "core/connection.py",
         "core/handle/sendAudioHandle.py", "core/handle/reportHandle.py", "core/utils/tts.py"]

raw = subprocess.check_output([
    "ssh", "aliyun-aipet", "docker exec xiaozhi-esp32-server tar cf - " + " ".join(FILES)])
archive = tarfile.open(fileobj=io.BytesIO(raw))
for name in FILES:
    output = STAGE / "candidate" / name
    output.parent.mkdir(parents=True, exist_ok=True)
    with archive.extractfile(name) as source:
        output.write_text(source.read().decode().replace("\r\n", "\n"), encoding="utf-8")
patch = subprocess.check_output(["git", "diff", BASE, "HEAD", "--"] + [
    str((SOURCE / name).relative_to(ROOT)).replace("\\", "/") for name in FILES], cwd=ROOT)
# --check 失败即停止；禁止覆盖线上不兼容的改动。
args = ["git", "apply", "--unsafe-paths", "--ignore-whitespace", "-p4",
        "--directory=" + str(STAGE / "candidate")]
subprocess.run(args + ["--check", "-"], input=patch, cwd=ROOT, check=True)
subprocess.run(args + ["-"], input=patch, cwd=ROOT, check=True)
(STAGE / "candidate/core/social_test_control.py").write_text(
    (SOURCE / "core/social_test_control.py").read_text(encoding="utf-8"), encoding="utf-8")
for name in ["pet_common/config.py", "web_api/social_test.py", "web_api/social_test_app.py",
             "web_api/routers/social_test.py"]:
    output = STAGE / "backend" / name
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text((ROOT.parent / "ai-pet-backend/src" / name).read_text(encoding="utf-8"),
                      encoding="utf-8")
print("候选上下文已生成；仍需在服务器构建、测试后切换")

from uuid import uuid4
import pytest

from app.services.ci_sandbox import CISandbox


def test_sandbox_docker_availability():
    assert CISandbox.is_docker_available() is True


def test_sandbox_legitimate_execution_compatibility():
    sandbox = CISandbox()
    res = sandbox.run_container_verification(
        job_id=str(uuid4()),
        commit_sha="1111111111111111111111111111111111111111",
        target_branch="main",
        custom_script="print('SUTRA Sandbox Test'); exit(0)",
    )

    assert res["exit_code"] == 0
    assert "SUTRA Sandbox Test" in res["output_log"]
    assert res["timed_out"] is False


def test_sandbox_network_isolation_attempt():
    sandbox = CISandbox()
    # Script attempts to connect to socket / localhost / PostgreSQL
    script = (
        "import socket, sys; "
        "s = socket.socket(); "
        "s.settimeout(2); "
        "res_err = s.connect_ex(('127.0.0.1', 55432)); "
        "print('NETWORK_RESULT_ERR:', res_err); "
        "sys.exit(0 if res_err != 0 else 1)"
    )
    res = sandbox.run_container_verification(
        job_id=str(uuid4()),
        commit_sha="1111111111111111111111111111111111111111",
        target_branch="main",
        custom_script=script,
    )

    assert res["exit_code"] == 0
    assert "NETWORK_RESULT_ERR: 111" in res["output_log"] or "NETWORK_RESULT_ERR:" in res["output_log"]
    assert "NETWORK_CONNECTED" not in res["output_log"]


def test_sandbox_environment_secret_isolation():
    sandbox = CISandbox()
    script = (
        "import os; "
        "keys = list(os.environ.keys()); "
        "print('ENV_KEYS:', keys); "
        "assert 'DATABASE_URL' not in os.environ; "
        "assert 'SECRET_KEY' not in os.environ; "
        "assert 'JWT_SECRET' not in os.environ; "
        "exit(0)"
    )
    res = sandbox.run_container_verification(
        job_id=str(uuid4()),
        commit_sha="1111111111111111111111111111111111111111",
        target_branch="main",
        custom_script=script,
    )

    assert res["exit_code"] == 0
    assert "DATABASE_URL" not in res["output_log"]
    assert "SECRET_KEY" not in res["output_log"]


def test_sandbox_docker_socket_and_host_filesystem_isolation():
    sandbox = CISandbox()
    script = (
        "import os; "
        "assert not os.path.exists('/var/run/docker.sock'), 'Docker socket exposed!'; "
        "assert not os.path.exists('/d/sutra'), 'Host directory exposed!'; "
        "assert os.getuid() != 0, 'Container running as root!'; "
        "print('ISOLATION_VERIFIED'); "
        "exit(0)"
    )
    res = sandbox.run_container_verification(
        job_id=str(uuid4()),
        commit_sha="1111111111111111111111111111111111111111",
        target_branch="main",
        custom_script=script,
    )

    assert res["exit_code"] == 0
    assert "ISOLATION_VERIFIED" in res["output_log"]


def test_sandbox_timeout_enforcement():
    sandbox = CISandbox()
    # Script attempts infinite loop
    script = "import time; time.sleep(40)"

    # Temporarily run with shorter timeout for fast test execution
    sandbox.TIMEOUT_SECONDS = 3
    res = sandbox.run_container_verification(
        job_id=str(uuid4()),
        commit_sha="1111111111111111111111111111111111111111",
        target_branch="main",
        custom_script=script,
    )

    assert res["timed_out"] is True
    assert res["exit_code"] == -1
    assert "exceeded 3 seconds" in res["output_log"]

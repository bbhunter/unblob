"""Dynamically generate test cases from files in the tests/integration directory.

Directories can be nested arbitrarily.
Each of the test folders should contain 2 things:
- The original file we want to test.
- Input files in the __input__ folder.
- The expected output in the __output__ folder.
"""

import inspect
import sys
from pathlib import Path

import pytest

from unblob import handlers
from unblob.models import Handler
from unblob.processing import ExtractionConfig, process_file
from unblob.sandbox import AccessFS, Sandbox
from unblob.testing import (
    check_output_is_the_same,
    check_result,
    gather_integration_tests,
)

TEST_DATA_PATH = Path(__file__).parent / "integration"
HANDLERS_PACKAGE_PATH = Path(handlers.__file__).parent


@pytest.mark.parametrize(
    "input_dir, output_dir", gather_integration_tests(TEST_DATA_PATH)
)
def test_all_handlers(
    input_dir: Path,
    output_dir: Path,
    extraction_config: ExtractionConfig,
    request: pytest.FixtureRequest,
):
    handler_name = input_dir.parent.name
    if (sys.platform, handler_name) == ("darwin", "partclone"):
        pytest.skip(
            f"Handler '{handler_name}' not supported on platform '{sys.platform}'"
        )

    log_path = Path("/dev/null")  # no logging
    report_file = None  # no reporting

    passthrough = [
        # .pytest_cache
        AccessFS.read_write(request.config.rootpath),
    ]
    junit_xmlpath = request.config.getvalue("xmlpath")
    if junit_xmlpath:
        passthrough += [
            # junit reports are written to the argument of --junit-xml
            AccessFS.read_write(junit_xmlpath)  # type: ignore
        ]

    sandbox = Sandbox(extraction_config, log_path, report_file, passthrough)
    for input_file in input_dir.iterdir():
        reports = sandbox.run(process_file, extraction_config, input_file)
        check_result(reports)

    check_output_is_the_same(output_dir, extraction_config.extract_root)


@pytest.mark.parametrize(
    "handler",
    (pytest.param(handler, id=handler.NAME) for handler in handlers.BUILTIN_HANDLERS),
)
def test_missing_handlers_integrations_tests(handler: type[Handler]):
    handler_module_path = Path(inspect.getfile(handler))
    handler_test_path = handler_module_path.relative_to(
        HANDLERS_PACKAGE_PATH
    ).with_suffix("")

    if handler_test_path.name == handler.NAME:
        # when there is 1 handler class in the handler module, with the same NAME as the module
        expected_test_path = handler_test_path
    else:
        expected_test_path = handler_test_path.joinpath(handler.NAME)

    test_path = TEST_DATA_PATH.joinpath(expected_test_path)
    if not test_path.exists():
        pytest.fail(
            f"Missing test for handler: {handler.NAME}. Searched in: {test_path}"
        )

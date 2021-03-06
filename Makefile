# Copyright (C) 2020 University of Glasgow
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

PYTHON_SRC   = $(wildcard npt/*.py)
PYTHON_TESTS = $(wildcard tests/*.py)

.PHONY: test unittests integrationtests

test: unittests integrationtests

# =================================================================================================
# The CI build runs the following in the python-testing environment:

test-results/typecheck.xml: $(PYTHON_SRC) $(PYTHON_TESTS)
	mypy npt/*.py tests/*.py --junit-xml test-results/typecheck.xml

unittests: test-results/typecheck.xml $(PYTHON_SRC) $(PYTHON_TESTS)
	@python3 -m unittest discover -s tests/ -v

tests/%/pcaps: tests/%/generate-pcaps.py
	mkdir -p tests/$(*)/pcaps
	cd tests/$(*) && python generate-pcaps.py

examples/output/draft/%/rust: examples/%.xml
	npt $< -of rust

# =================================================================================================
# The CI build runs the following in the rust-testing environment:

integrationtests: examples/output/draft/draft-mcquistin-simple-example/rust tests/simple-protocol-testing/pcaps examples/output/draft/draft-mcquistin-augmented-udp-example/rust tests/udp-testing/pcaps
	cd tests/simple-protocol-testing/testharness && cargo test
	cd tests/udp-testing/udp-testharness && cargo test

# =================================================================================================

clean:
	rm -f  test-results/typecheck.xml
	rm -fr examples/output

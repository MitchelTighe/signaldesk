#!/bin/sh
# Only this preparatory step needs registry access. No image build or host install.
set -eu
exec podman pull "${SIGNALDESK_IMAGE:-docker.io/library/python@sha256:2986c55feb36e6cae00fa1fefb454283e4b33f35e75ff8bdd123b134130be301}"

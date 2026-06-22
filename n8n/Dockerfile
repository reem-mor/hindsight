# n8n + the Python deps the Execute Command extractor needs (PyMuPDF, python-docx).
# The stock n8n image is Node-only, so the postmortem extractor can't run on it as-is.
#
# As of late 2025 the official n8n image is a Docker Hardened Image (Alpine with the
# apk package manager stripped out for security), so `apk add python3` no longer works.
# Instead we build the Python runtime + libraries in a matching alpine:3.22 stage and
# copy them in. Both images are Alpine/musl, so the binaries and shared libs line up.

FROM alpine:3.22 AS pybuild
RUN apk add --no-cache python3 py3-pip libstdc++ libgcc \
 && pip install --no-cache-dir --break-system-packages --target=/pydeps \
      PyMuPDF==1.24.10 python-docx==1.1.2

FROM docker.n8n.io/n8nio/n8n:latest

USER root

# Python interpreter + stdlib, the libs PyMuPDF links against, and the two packages.
COPY --from=pybuild /usr/bin/python3.12 /usr/bin/python3.12
COPY --from=pybuild /usr/lib/python3.12 /usr/lib/python3.12
COPY --from=pybuild /usr/lib/libpython3.12.so.1.0 /usr/lib/
COPY --from=pybuild /usr/lib/libstdc++.so.6 /usr/lib/
COPY --from=pybuild /usr/lib/libgcc_s.so.1 /usr/lib/
COPY --from=pybuild /pydeps /opt/pydeps
RUN ln -sf /usr/bin/python3.12 /usr/bin/python3
ENV PYTHONPATH=/opt/pydeps

USER node

# n8n + the Python deps the Execute Command extractor needs (PyMuPDF, python-docx).
# The stock n8n image is Node-only, so the postmortem extractor can't run on it as-is.
FROM docker.n8n.io/n8nio/n8n:latest

USER root

# python3 + pip, then the two libraries the extractor imports.
# PyMuPDF ships musllinux wheels, so this installs without a compiler on Alpine.
RUN apk add --no-cache python3 py3-pip \
 && pip install --no-cache-dir --break-system-packages PyMuPDF==1.24.10 python-docx==1.1.2

USER node

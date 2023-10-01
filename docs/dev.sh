#!/bin/bash

tmux new-session -d -s docs-server "python3 -m http.server --bind 127.0.0.1 -d build/html 8000"

inotifywait -r -m -e modify $(find . -name "*.py" -or -name "*.rst" -or -name "Makefile" | xargs) |
    while read ; do
        SYCURICON_SPHINX_MODE=DEBUG proxychains make html;
    done

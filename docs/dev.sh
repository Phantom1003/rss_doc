#!/bin/bash

echo "Launching a HTTP server in another terminal..."
echo "  $ python3 -m http.server -d build/html"

inotifywait -r -m -e modify $(find . -name "*.py" -or -name "*.rst" -or -name "Makefile" | xargs) |
        while read ; do
            SYCURICON_SPHINX_MODE=DEBUG proxychains make html
        done

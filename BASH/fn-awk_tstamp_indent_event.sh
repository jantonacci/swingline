#!/bin/bash
#
# Send messages to STDOUT using awk to create VMWare hostd multiline logged event format

TSTAMP=$(date +"%Y-%m-%dT%T.%3N%z")
TARGET="$HOME/test.txt"

if [ -e "$TARGET" ]; then
  stat $TARGET | awk -v var=$TSTAMP '{NR<=1 sub(/^/, var); NR<=1 || sub(/^/, " -->\t"); print}'
else
    echo "Exited.  File \"$TARGET\" does not exist. Run:"
    echo "touch \"$TARGET\""
fi

#EOF

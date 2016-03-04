#!/bin/bash
#
# Function to return script usage, incl. command line options and arguements

# Use Google's Shell Style Guide: https://google-styleguide.googlecode.com/svn/trunk/shell.xml

#######################################
# Return formatted text with script usage
# Globals:
#   None
# Arguments:
#   None
# Returns:
#   None
#######################################
usage() {
cat << EOF
usage: $0 options

This script does [...]

OPTIONS:
   -h      Show this message
   -o      Output written to provided file path
EOF
}

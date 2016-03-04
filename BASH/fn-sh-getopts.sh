#!/bin/bash
#
# Function to parse mutliple command line options and arguements

# Use Google's Shell Style Guide: https://google-styleguide.googlecode.com/svn/trunk/shell.xml

# NOTE1: Recommendations exist to never use getopt (no 's') unless it's the util-linux package's enhanced version.
# Traditional versions of getopt cannot handle empty argument strings, or arguments with whitespace without quotes.
# The POSIX shell getopts (notice the 's') is safer, but does not support long arguements (ex. --option=value).

# NOTE2: This script does work in BusyBox or ESXi

readonly USAGE="Print script usage. Exit."

#######################################
# Parse command line options and agruements then configure corresponding script options
# Globals:
#   USAGE
# Arguments:
#   $@ (command line arguements array)
# Returns:
#   None
#######################################
process_optargs() {
  while getopts “ho:” OPTION
  do
    case $OPTION in
      h)
        echo -e "\n${USAGE}"  # Alternatively, call a script usage function; see usage.sh
        exit 0
        ;;
      o)
        echo -e "\nSet variable PATH_TO_OUTPUT_FILE with value \"${OPTARG}\""
        PATH_TO_OUTPUT_FILE="${OPTARG}"  # Assign option arguement to variable
        ;;
      esac
  done
  shift $(($OPTIND - 1))

  if [ -z $PATH_TO_OUTPUT_FILE ]; then
    echo -e "\n${USAGE}"  # Alternatively, call a script usage function; see usage.sh
    exit 1
  fi
} # end function process_cli_args

#######################################
# Main function
# Globals:
#   To Be Determined
# Arguments:
#   $@ (command line arguements array)
# Returns:
#   None
#######################################
main() {
  process_optargs "${@}"    #function call
} # end function main

main "${@}"

#EOF

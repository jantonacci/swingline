#!/bin/bash
#
# Function to parse mutliple command line options and arguements

# Use Google's Shell Style Guide: https://google-styleguide.googlecode.com/svn/trunk/shell.xml

# NOTE1: Recommendations exist to never use getopt (no 's') unless it's the util-linux package's enhanced version.
# Traditional versions of getopt cannot handle empty argument strings, or arguments with whitespace without quotes.
# The POSIX shell getopts (notice the 's') is safer, but does not support long arguements (ex. --option=value).

# NOTE2: This script does  not work in BusyBox or ESXi

readonly USAGE="Print script usage. Exit."

#######################################
# Parse arguements from command line and configure corresponding script options
# Globals:
#   USAGE
# Arguments:
#   $@ (command line arguements array)
# Returns:
#   None
#######################################
process_optargs() {
  ## NOTE: This requires GNU getopt; BASH built-in getopts is not equivalent
  local strGetOpt=$(getopt --options ho: --longoptions help,output: -- "${@}")

  $(set -- ${strGetOpt})

  while [[ $# -gt 0 ]]; do
    case "${1}" in
      # This option has no arguements. Print script usage.
      -h | --help )
        echo -e "\n${USAGE}"  # Alternatively, call a script usage function; see usage.sh
        exit 0
        ;;
      # This option has an arguement. Output to a file.
      -o | --output)
        echo -e "\nSet variable PATH_TO_OUTPUT_FILE with value \"${2}\""
        PATH_TO_OUTPUT_FILE="${2}"  # Assign option arguement to variable
        ;;
      -- )
        echo -e "\nAll options processed."
        break
        ;;
    esac
    shift
  done

  # get rid of the just-finished flag arguments
  shift $((${OPTIND}-1))
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

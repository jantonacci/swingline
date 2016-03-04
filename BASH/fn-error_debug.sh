#!/bin/bash
#
# Send messages to STDERR using pipe

#######################################
# Send messsages to STDERR using...
#   echo "message" | error
# Globals:
#   None
# Arguments:
#   None
# Returns:
#   None
#######################################
error() {
  cat - >&2
}

#######################################
# Send messsages to STDERR if debug variable set using...
#   echo "message" | debug
# Globals:
#   DEBUG_ON
# Arguments:
#   None
# Returns:
#   None
#######################################
debug() {
  if [[ -n $DEBUG_ON ]] ; then
      cat - >&2
  fi
}

#######################################
# Main
# Globals:
#   boolDebug
# Arguments:
#   None
# Returns:
#   None
#######################################
main() {
  echo "Error message." | error # Message to STDERR

  # Variable DEBUG_ON can be set using command line options; see fn-gnu-getopt.sh
  DEBUG_ON='true'
  echo "Debug message." | debug # Message to STDERR
  unset DEBUG_ON
  echo "Debug message." | debug # No message to STDERR
}

main

#EOF

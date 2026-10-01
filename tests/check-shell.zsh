#!/usr/bin/env zsh
# Run only after bootstrap: zsh -i tests/check-shell.zsh generic|personal
set -eu
case "${1:-}" in
    generic)
        [[ "$WORKSTATION_GITHUB" == 0 && "$WORKSTATION_CLOUD" == 0 ]]
        (( ! ${plugins[(Ie)gh]} && ! ${plugins[(Ie)gcloud]} ))
        (( ! ${+aliases[devvaultupdate]} ))
        ;;
    personal)
        [[ "$WORKSTATION_GITHUB" == 1 && "$WORKSTATION_CLOUD" == 1 ]]
        (( ${plugins[(Ie)gh]} && ${plugins[(Ie)gcloud]} ))
        (( ${+aliases[devvaultupdate]} ))
        ;;
    *) exit 2 ;;
esac
(( ${+aliases[devdoctor]} && ${+aliases[devprofile]} && ${+aliases[devrestore]} ))
(( ${+aliases[devconfig]} && ${+aliases[devcheck]} && ${+aliases[updateall]} ))
print 'Shell capabilities and aliases verified.'

#!/bin/bash
DIR="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
curl http://s3.amazonaws.com/wikia_xml_dumps/e/en/enmemoryalpha_pages_current.xml.gz | gunzip > $DIR/memory_alpha.xml

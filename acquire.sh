#!/bin/bash
curl http://s3.amazonaws.com/wikia_xml_dumps/e/en/enmemoryalpha_pages_current.xml.gz | gunzip > memory_alpha.xml
portiacrawl ~/Development/dfwpython/crawlers/star_trek/ wikipedia -o wikipedia.json -t json

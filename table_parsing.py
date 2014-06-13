# Standard Library
import json
import re
import sqlite3
import string
# Third Party
import lxml.etree
import lxml.html

FILM_MAP = {'TMP': 'Star Trek: The Motion Picture (1979)',
            'WOK': 'Star Trek II: The Wrath of Khan (1982)',
            'SFS': 'Star Trek III: The Search for Spock (1984)',
            'TVH': 'Star Trek IV: The Voyage Home (1986)',
            'TFF': 'Star Trek V: The Final Frontier (1989)',
            'TUC': 'Star Trek VI: The Undiscovered Country (1991)',
            'GEN': 'Star Trek Generations (1994)',
            'FCT': 'Star Trek: First Contact (1996)',
            'INS': 'Star Trek: Insurrection (1998)',
            'NEM': 'Star Trek: Nemesis (2002)',
            'ST': 'Star Trek (2009)',
            'ID': 'Star Trek Into Darkness (2013)'}
CHARACTERS_STMT = 'INSERT INTO characters VALUES (?)'
EPISODES_STMT = 'INSERT INTO episodes VALUES (?, ?)'

with open('wikipedia.json') as js_fo:
    raw_data = json.load(js_fo)

conn = sqlite3.connect(':memory:')
conn.execute('CREATE TABLE characters (name text);')
conn.execute('CREATE TABLE episodes (name text, episode text);')

for spider in raw_data:
    for table_str in spider['table']:
        table_str = u'<table>{}</table>'.format(table_str)
        elem = lxml.html.fragment_fromstring(table_str)
        for count, row in enumerate(elem.findall('tr')[2:]):
            if not count % 2:
                cells = row.getchildren()
                character = cells[0].text
                conn.execute(CHARACTERS_STMT, (character,))
                episodes = unicode(cells[2].text_content())
                episodes = episodes.replace(') ', ')\n').replace('),', ')\n')
                episodes = episodes.replace('recurring thereafter,',
                                            'recurring thereafter\n')

                episodes = re.sub(r'([A-Z]{2,3}), ', r'\1\n', episodes)
                for episode in (x for x in episodes.split('\n') if x):
                    name = FILM_MAP.get(episode, episode)
                    conn.execute(EPISODES_STMT, (character, name))

print conn.execute('SELECT COUNT(*) FROM characters').fetchall()
print conn.execute('SELECT COUNT(*) FROM episodes').fetchall()

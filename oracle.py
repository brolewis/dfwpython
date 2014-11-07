#!/usr/bin/env python2.7
# Standard Library
import argparse
import collections
import os
import re
import xml.etree.cElementTree
# Third Party
import imdb
import imdb.helpers
import mediawiki
import sqlalchemy
import sqlalchemy.ext.declarative
import sqlalchemy.ext.hybrid
import sqlalchemy.orm


CANON = {'"Star Trek" (1966)': 'TOS',
         '"Star Trek: The Next Generation" (1987)': 'TNG',
         '"Star Trek: Voyager" (1995)': 'VOY',
         '"Star Trek: Enterprise" (2001)': 'ENT',
         '"Star Trek" (1973)': 'TAS',
         '"Star Trek: Deep Space Nine" (1993)': 'DS9',
         'Star Trek: The Motion Picture (1979)': '',
         'Star Trek II: The Wrath of Khan (1982)': '',
         'Star Trek III: The Search for Spock (1984)': '',
         'Star Trek IV: The Voyage Home (1986)': '',
         'Star Trek V: The Final Frontier (1989)': '',
         'Star Trek VI: The Undiscovered Country (1991)': '',
         'Star Trek: Generations (1994)': '',
         'Star Trek: First Contact (1996)': '',
         'Star Trek: Insurrection (1998)': '',
         'Star Trek: Nemesis (2002)': '',
         'Star Trek (2009)': '',
         'Star Trek Into Darkness (2013)': ''}
BASE = sqlalchemy.ext.declarative.declarative_base()


association_table = sqlalchemy.Table('character_appearance', BASE.metadata,
    sqlalchemy.Column('character_id', sqlalchemy.Integer,
                      sqlalchemy.ForeignKey('character.id')),
    sqlalchemy.Column('appearance_id', sqlalchemy.Integer,
                      sqlalchemy.ForeignKey('appearance.id'))
)


class Character(BASE):
    __tablename__ = 'character'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    role_id = sqlalchemy.Column(sqlalchemy.String, unique=True)
    name = sqlalchemy.Column(sqlalchemy.String)
    article = sqlalchemy.orm.relationship('Article', uselist=False,
                                          backref='character')
    appearances = sqlalchemy.orm.relationship('Appearance',
                                              secondary=association_table,
                                              backref='characters')

    def __repr__(self):
        return self.name


class Appearance(BASE):
    __tablename__ = 'appearance'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    title = sqlalchemy.Column(sqlalchemy.String)
    kind = sqlalchemy.Column(sqlalchemy.String)
    article = sqlalchemy.orm.relationship('Article', uselist=False,
                                          backref='appearance')

    def __repr__(self):
        return self.title


class Article(BASE):
    __tablename__ = 'article'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    title = sqlalchemy.Column(sqlalchemy.String)
    text = sqlalchemy.Column(sqlalchemy.String)
    character_id = sqlalchemy.Column(sqlalchemy.Integer,
                                     sqlalchemy.ForeignKey('character.id'))
    appearance_id = sqlalchemy.Column(sqlalchemy.Integer,
                                      sqlalchemy.ForeignKey('appearance.id'))

    def __repr__(self):
        return self.title

    @sqlalchemy.ext.hybrid.hybrid_property
    def html(self):
        return mediawiki.wiki2html(self.text or '', False)


class SixDegrees(object):
    def __init__(self):
        database_uri = os.getenv('DATABASE_URI', 'sqlite:///star_trek.sqlite')
        engine = sqlalchemy.create_engine(database_uri)
        BASE.metadata.create_all(engine)
        self.session = sqlalchemy.orm.sessionmaker(bind=engine)()
        self._role_names = None

    def load_imdb(self):
        access = imdb.IMDb()
        self._role_names = collections.defaultdict(list)
        for series in access.search_movie('Star Trek', results=30):
            title = series['long imdb title']
            kind = series['kind']
            if title in CANON:
                if kind == 'tv series':
                    title = CANON[title]
                    access.update(series, 'episodes')
                    for episode in imdb.helpers.sortedEpisodes(series):
                        access.update(episode)
                        self._parse_episode(episode, title, kind)
                elif kind == 'movie':
                    appearance = self._get_appearance(title, kind)
                    movie = access.get_movie(series.movieID)
                    for actor in movie['cast']:
                        self._add_actor(actor, appearance)
                    self.session.add(appearance)
                    self.session.commit()
        for role_id in self._role_names:
            counter = collections.Counter(self._role_names[role_id])
            query = self.session.query(Character)
            character = query.filter_by(role_id=role_id).first()
            character.name = counter.most_common(1)[0][0]
        self.session.commit()

    def _parse_episode(self, episode, series_title, series_kind):
        episode_title = u'{} ({})'.format(episode['title'], series_title)
        appearance = self._get_appearance(episode_title, series_kind)
        for actor in episode['cast']:
            self._add_actor(actor, appearance)
        self.session.add(appearance)
        self.session.commit()

    def _add_actor(self, actor, appearance):
        if isinstance(actor.currentRole, imdb.utils.RolesList):
            for role in actor.currentRole:
                character = self._add_character(role)
                if character:
                    appearance.characters.append(character)
        else:
            character = self._add_character(actor.currentRole)
            if character:
                appearance.characters.append(character)

    def _add_character(self, role):
        generic = ('Enterprise Computer', 'Ensign', 'Starfleet Officer')
        if role.get('name') and role.getID() and role['name'] not in generic:
            self._role_names[role.getID()].append(role['name'])
            query = self.session.query(Character)
            character = query.filter_by(role_id=role.getID()).first()
            if not character:
                character = Character(role_id=role.getID(), name=role['name'])
                self.session.add(character)
                self.session.commit()
            return character

    def _get_appearance(self, title, kind):
        query = self.session.query(Appearance)
        appearance = query.filter_by(title=title).first()
        if not appearance:
            appearance = Appearance(title=title, kind=kind)
            self.session.add(appearance)
        return appearance

    def load_ma(self):
        name_pattern = re.compile(r'(?:\{.*\}){0,1}(.*)')
        slug_pattern = re.compile(r'[\W_]+')
        slugs = self.slugs
        xml_dir = os.path.basename(os.path.realpath(__file__))
        xml_path = os.path.join(xml_dir, 'memory_alpha.xml')
        events = ('start', 'end')
        etree = xml.etree.cElementTree.iterparse(xml_path, events=events)
        level = -1
        for event, elem in etree:
            name = name_pattern.search(elem.tag).groups()[0]
            if event == 'start':
                level += 1
            if level == 2 and event == 'end' and name == 'title':
                title = elem.text
            if level == 3 and event == 'end' and name == 'text':
                text = elem.text
            if level == 1 and event == 'end':
                if name == 'page':
                    slug = slug_pattern.sub('', title).lower()
                    if slug in slugs:
                        obj = slugs[slug]
                        article = Article(title=title, text=text)
                        if isinstance(obj, Appearance):
                            article.appearance = obj
                        else:
                            article.character = obj
                        self.session.add(article)
                        self.session.commit()
            if event == 'end':
                level -= 1
                elem.clear()

    @property
    def slugs(self):
        pattern = re.compile(r'[\W_]+')
        slugs = {}
        for appearance in self.session.query(Appearance).all():
            slug = pattern.sub(u'', appearance.title.split('(')[0]).lower()
            slug = slug.replace(u'part1', u'parti').replace(u'part2', u'partii')
            if appearance.kind == 'movie':
                slugs[slug] = appearance
            else:
                slug += u'episode'
                slugs[slug] = appearance
                if 'parti' in slug:
                    slugs[slug.replace(u'parti', u'')] = appearance
        for character in self.session.query(Character).all():
            slugs[pattern.sub('', character.name).lower()] = character
        return slugs

    def get_character(self, name):
        name_filter = '%{}%'.format(name.replace(' ', '%').replace('.', ''))
        query = self.session.query(Character)
        return query.filter(Character.name.like(name_filter)).first()

    def all_characters(self):
        return self.session.query(Character).all()

    def find_connection(self, start_name, end_name):
        link = self._shortest_link(start_name, end_name)
        if not link:
            return link
        complete_link = []
        for count, character in enumerate(link):
            if count:
                appearance = self._direct_link(link[count - 1], character)
                complete_link.append((appearance, character))
        return complete_link

    def _shortest_link(self, start_name, end_name):
        if start_name == end_name:
            return []
        start_character = self.get_character(start_name)
        end_character = self.get_character(end_name)
        if not (start_character or end_character):
            return []
        investigated = [end_character]
        to_investigate = [[end_character]]
        distance = 0
        while to_investigate:
            character_link = to_investigate[0]
            character = character_link[distance]
            for appearance in character.appearances:
                for co_star in appearance.characters:
                    if co_star not in investigated:
                        if co_star == start_character:
                            character_link.append(co_star)
                            return character_link
                        elif co_star not in investigated:
                            investigated.append(co_star)
                            full_link = character_link[:]
                            full_link.append(co_star)
                            to_investigate.append(full_link)
            to_investigate.remove(character_link)
            if _minimum(to_investigate) == distance + 2:
                distance += 1
        return []

    def _direct_link(self, start_character, end_character):
        for appearance in start_character.appearances:
            if end_character in appearance.characters:
                return appearance

    def find_article(self, obj):
        pass


def _minimum(L):
    smallest = 'z'
    for sublist in L:
        smallest = min(smallest, len(sublist))
    return smallest


def play():
    while True:
        start_name = 'Captain James T. Kirk'
        message = 'Please enter character name (or press Enter to exit): '
        end_name = raw_input(message)
        character = six.get_character(end_name)
        if end_name == '':
            print 'Thank you for playing!'
            break
        elif character.name == start_name:
            print u'{} has a Kirk Number of 0.'.format(character)
        else:
            full_link = six.find_connection(start_name, end_name)
            if len(full_link):
                message = '{} has a Kirk Number of {}'
                print message.format(end_name, len(full_link))
                previous = character
                for sublink in full_link:
                    appearance, character = sublink
                    message = '\t{} was in {} with {}.'
                    print message.format(previous, appearance, character)
                    previous = character
            else:
                print '{} has a Kirk Number of Infinity.'.format(end_name)
        print '\n',


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Six Degress of Captain Kirk')
    parser.add_argument('--load_data', action='store_true', help='Query IMDB')
    args = parser.parse_args()
    six = SixDegrees()
    if args.load_data:
        six.load_imdb()
        six.load_ma()
    else:
        play()

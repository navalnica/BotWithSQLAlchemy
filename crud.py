import logging
from contextlib import contextmanager

import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URI
from models import Person

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

engine = create_engine(DATABASE_URI)
session_factory = sessionmaker(bind=engine)


@contextmanager
def session_scope():
    # TODO: add optional commit
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def load_yaml_family():
    with session_scope() as ss:
        for data in yaml.safe_load_all(open('./src/sqa_test/person.yaml')):
            person = Person(**data)
            ss.add(person)


def add_person(p: Person):
    with session_scope() as ss:
        ss.add(p)


def delete_person(p: Person):
    with session_scope() as ss:
        num_deleted = ss.query(Person).filter(Person.name == p.name, Person.age == p.age).delete()
    return num_deleted


def get_all_persons():
    session = session_factory()
    res = session.query(Person).order_by(Person.id).all()
    session.close()
    return res


def edit_person(old_person_id, new_person):
    with session_scope() as ss:
        old_person = ss.query(Person).filter(Person.id == old_person_id).first()
        old_person.name = new_person.name
        old_person.age = new_person.age


def print_persons(persons):
    print('\n'.join(map(str, persons)))


def main():
    # Base.metadata.tables['person'].drop(engine, checkfirst=True)
    # Base.metadata.tables['person'].create(engine, checkfirst=True)
    # load_yaml_family()

    with session_scope() as ss:
        pl = [Person(name='lies', age=16 + i) for i in range(100)]
        ss.add_all(pl)


if __name__ == '__main__':
    main()

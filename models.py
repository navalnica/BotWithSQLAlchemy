from sqlalchemy import Column, Integer, String, Date
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Book(Base):
    __tablename__ = 'books'

    id = Column(Integer, primary_key=True)
    title = Column(String)
    author = Column(String)
    pages = Column(Integer)
    published = Column(Date)

    def __repr__(self):
        return f'<Book(title="{self.title}", author="{self.author}", ' \
               f'pages={self.pages}, published={self.published})>'


class Person(Base):
    __tablename__ = 'person'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    age = Column(Integer)

    def __repr__(self):
        return f'Person(id={self.id}, name={self.name}, age={self.age})'

    def __str__(self):
        return f'{self.name}, {self.age}'

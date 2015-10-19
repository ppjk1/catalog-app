import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dbsetup import Base, User, Category, Item

engine = create_engine('sqlite:///catalog.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()


user1 = User(name="Jonathan Hunter", email="popejacki@gmail.com")

category1 = Category(name="Acoustic Guitars", permalink="acoustic-guitars")
category2 = Category(name="Electric Guitars", permalink="electric-guitars")
category3 = Category(name="Bass Guitars", permalink="bass-guitars")
category4 = Category(name="Ukeleles", permalink="ukeleles")
category5 = Category(name="Mandolins", permalink="mandolins")
category6 = Category(name="Banjos", permalink="banjos")
category7 = Category(name="Guitar Amplifiers", permalink="guitar-amplifiers")
category8 = Category(name="Effects Pedals", permalink="effects-pedals")
category9 = Category(name="Drums", permalink="drums")

session.add(category1)
session.add(category2)
session.add(category3)
session.add(category4)
session.add(category5)
session.add(category6)
session.add(category7)
session.add(category8)
session.add(category9)
session.commit()

item1 = Item(name = "Awesome Acoustic Guitar",
             permalink = "awesome-acoustic-guitar",
             description = "An awesome acoustic guitar.",
             picture = "acoustic-guitar.jpg",
             created_at = datetime.datetime.now(),
             category = category1,
             user = user1)

item2 = Item(name = "Sublime Electric Guitar",
             permalink = "sublime-electric-guitar",
             description = "A sublime electric guitar.",
             picture = "electric-guitar.jpg",
             created_at = datetime.datetime.now(),
             category = category2,
             user = user1)

item3 = Item(name = "Wunderkind Bass Guitar",
             permalink = "wunderkind-bass-guitar",
             description = "A bass guitar for wunderkinds.",
             picture = "bass-guitar.jpg",
             created_at = datetime.datetime.now(),
             category = category3,
             user = user1)

item4 = Item(name = "Unholy Ukelele",
             permalink = "unholy-ukelele",
             description = "An unholy ukelele.",
             picture = "ukelele.jpg",
             created_at = datetime.datetime.now(),
             category = category4,
             user = user1)

item5 = Item(name = "Merry Mandolin",
             permalink = "merry-mandolin",
             description = "The merriest of mandolins.",
             picture = "mandolin.jpg",
             created_at = datetime.datetime.now(),
             category = category5,
             user = user1)

item6 = Item(name = "Blistering Banjo",
             permalink = "blistering-banjo",
             description = "A blistering banjo.",
             picture = "banjo.jpg",
             created_at = datetime.datetime.now(),
             category = category6,
             user = user1)

item7 = Item(name = "High Altitude Amplifier",
             permalink = "high-altitude-amplifier",
             description = "A guitar amp for the heights.",
             picture = "guitar-amp.jpg",
             created_at = datetime.datetime.now(),
             category = category7,
             user = user1)

item8 = Item(name = "Effects Pedals in Triplicate",
             permalink = "effects-pedals-in-triplicate",
             description = "More effects pedals than you could ever want.",
             picture = "pedals.jpg",
             created_at = datetime.datetime.now(),
             category = category8,
             user = user1)

item9 = Item(name = "The Pounding Drums",
             permalink = "the-pounding-drums",
             description = "A drum for every occasion.",
             picture = "drums.jpg",
             created_at = datetime.datetime.now(),
             category = category9,
             user = user1)

session.add(item1)
session.add(item2)
session.add(item3)
session.add(item4)
session.add(item5)
session.add(item6)
session.add(item7)
session.add(item8)
session.add(item9)
session.commit()

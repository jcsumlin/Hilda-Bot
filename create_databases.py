import os

from loguru import logger
from sqlalchemy import Column, Integer, String, Date, Boolean, Float
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
 
class User(Base):
    __tablename__ = 'user'
    # Here we define columns for the table person
    # Notice that each column is also a normal Python instance attribute.
    id = Column(String, nullable=False, primary_key=True)
    name = Column(String(40), nullable=False) #names can't be more than 32 characters on discord anyway
    server_id = Column(String, nullable=False)
    startdate = Column(Date, nullable=False)
    level = Column(Integer, nullable=False)
    currency = Column(Integer, nullable=False)
    streak = Column(Integer, nullable=False)
    expiry = Column(Date, nullable=False)
    submitted = Column(Boolean, nullable=False)
    special_event_submitted = Column(Boolean, nullable=False)
    raffle = Column(Boolean, nullable=False)
    promptsadded = Column(Integer, nullable=False)
    totalsubmissions = Column(Integer, nullable=False)
    currentxp = Column(Integer, nullable=False)
    adores = Column(Integer, nullable=False)
    highscore = Column(Integer, nullable=False)
    decaywarning = Column(Boolean, nullable=False)
    levelnotification = Column(Boolean, nullable=False, default=True)
    xptime = Column(Float, nullable=False)


class Content(Base):
    __tablename__ = 'content'
    submission_id = Column(Integer, autoincrement=True, primary_key=True)
    message_id = Column(String, unique=True, nullable=False)
    user = Column(String, nullable=False)
    datesubmitted = Column(String, nullable=False)
    link = Column(String, nullable=False)
    score = Column(Integer, default=0, nullable=False)
    comment = Column(String, nullable=False, default="")
    xpfromcontent = Column(Integer, nullable=False)
    event_id = Column(Integer)


class SpecialEvents(Base):
    __tablename__ = 'special_events'
    id = Column(Integer, primary_key=True)
    name = Column(String)

 
# Create an engine that stores data in the local directory's
# sqlalchemy_example.db file.
engine = create_engine('sqlite:///database.db')
 
# Create all tables in the engine. This is equivalent to "Create Table"
# statements in raw SQL.
Base.metadata.create_all(bind=engine)
logger.success("Database file 'database.db' has been created")
# moves database to correct folder for bot to function
if __name__ == '__main__':
    try:
        os.rename('./database.db', './cogs/database.db')
        logger.success("database.db has been moved into the cogs folder")
    except Exception as e:
        logger.error("Unable to move database, please ensure that you have proper permissions "
                     f"for this folder and its files. Error {e}")

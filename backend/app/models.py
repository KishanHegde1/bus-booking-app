from sqlalchemy import Column, Integer, String, Float
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    full_name = Column(String)
    email = Column(String)
    phone = Column(String)
    password_hash = Column(String)

    role = Column(String, default="customer")

class Bus(Base):
    __tablename__ = "buses"

    id = Column(Integer, primary_key=True, index=True)
    bus_name = Column(String)
    bus_number = Column(String)
    source = Column(String)
    destination = Column(String)
    departure_time = Column(String)
    arrival_time = Column(String)
    fare = Column(Float)
    total_seats = Column(Integer)

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer)
    bus_id = Column(Integer)

    seat_number = Column(String)

    passenger_name = Column(String)
    passenger_age = Column(Integer)

    journey_date = Column(String)

    booking_status = Column(String)
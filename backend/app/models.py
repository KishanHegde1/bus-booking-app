from sqlalchemy import Column, Integer, String, Float, DateTime
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

    total_route_distance = Column(Integer)

class BusStop(Base):
    __tablename__ = "bus_stops"
    id = Column(Integer, primary_key=True, index=True)
    bus_id = Column(Integer)
    stop_name = Column(String)
    stop_order = Column(Integer)
    distance_from_source = Column(Integer)
    arrival_time = Column(String, nullable=True)
    departure_time = Column(String, nullable=True)

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

class SeatLock(Base):
    __tablename__ = "seat_locks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    bus_id = Column(Integer)
    seat_number = Column(String)
    journey_date = Column(String)
    locked_at = Column(DateTime)
    expires_at = Column(DateTime)
    status = Column(String, default="LOCKED")
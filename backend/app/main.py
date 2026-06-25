from fastapi import FastAPI
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Bus, User, Booking, BusStop, SeatLock
from datetime import datetime, timedelta

from .schemas import (
    UserRegister,
    UserLogin,
    BookingRequest,
    BusCreate,
    UpdateProfileRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    SeatLockRequest,
    ReleaseSeatRequest
)

app = FastAPI()


@app.get("/")
def home():
    return {
        "message": "BUS APP Backend Running"
    }


@app.get("/buses")
def get_buses():

    db: Session = SessionLocal()

    buses = db.query(Bus).all()

    result = []

    for bus in buses:
        result.append({
            "id": bus.id,
            "bus_name": bus.bus_name,
            "bus_number": bus.bus_number,
            "source": bus.source,
            "destination": bus.destination,
            "fare": bus.fare
        })

    db.close()

    return result


@app.post("/register")
def register(user: UserRegister):

    db = SessionLocal()

    existing_user = db.query(User).filter(
        User.email == user.email
    ).first()

    if existing_user:
        db.close()
        return {
            "message": "Email already registered"
        }

    new_user = User(
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        password_hash=user.password
    )

    db.add(new_user)
    db.commit()

    db.close()

    return {
        "message": "User registered successfully"
    }

@app.post("/login")
def login(user: UserLogin):

    db = SessionLocal()

    existing_user = db.query(User).filter(
        User.email == user.email
    ).first()

    if not existing_user:
        db.close()
        return {
            "success": False,
            "message": "User not found"
        }

    if existing_user.password_hash != user.password:
        db.close()
        return {
            "success": False,
            "message": "Invalid password"
        }

    db.close()

    return {
    "success": True,
    "message": "Login successful",
    "user_id": existing_user.id,
    "name": existing_user.full_name,
    "email": existing_user.email,
    "role": existing_user.role
}

@app.get("/search-buses")
def search_buses(
    source: str,
    destination: str
):

    db = SessionLocal()

    buses = db.query(Bus).all()

    result = []

    for bus in buses:

        stops = db.query(BusStop).filter(
            BusStop.bus_id == bus.id
        ).order_by(
            BusStop.stop_order
        ).all()

        source_order = None
        destination_order = None

        source_distance = None
        destination_distance = None

        for stop in stops:

            if stop.stop_name.lower() == source.lower():

                source_order = stop.stop_order
                source_distance = stop.distance_from_source

            if stop.stop_name.lower() == destination.lower():

                destination_order = stop.stop_order
                destination_distance = stop.distance_from_source

        if (
            source_order is not None and
            destination_order is not None and
            source_order < destination_order
        ):

            journey_distance = (
                destination_distance -
                source_distance
            )

            calculated_fare = round(
                (
                    journey_distance /
                    bus.total_route_distance
                ) * bus.fare
            )

            result.append({
                "id": bus.id,
                "bus_name": bus.bus_name,
                "bus_number": bus.bus_number,
                "source": source,
                "destination": destination,
                "departure_time": str(bus.departure_time),
                "arrival_time": str(bus.arrival_time),
                "fare": calculated_fare,
                "journey_distance": journey_distance,
                "total_seats": bus.total_seats
            })

    db.close()

    return result

@app.post("/book-ticket")
def book_ticket(data: BookingRequest):

    db = SessionLocal()

    # Check if seat is already permanently booked
    existing_booking = db.query(Booking).filter(
        Booking.bus_id == data.bus_id,
        Booking.seat_number == data.seat_number,
        Booking.journey_date == data.journey_date,
        Booking.booking_status == "CONFIRMED"
    ).first()

    if existing_booking:

        db.close()

        return {
            "success": False,
            "message": "Seat already booked"
        }

    # Check whether this seat is locked by this user
    seat_lock = db.query(SeatLock).filter(
        SeatLock.user_id == data.user_id,
        SeatLock.bus_id == data.bus_id,
        SeatLock.seat_number == data.seat_number,
        SeatLock.journey_date == data.journey_date,
        SeatLock.status == "LOCKED",
        SeatLock.expires_at > datetime.now()
    ).first()

    if not seat_lock:

        db.close()

        return {
            "success": False,
            "message": "Seat lock expired. Please select seat again."
        }

    # Create Booking
    booking = Booking(
        user_id=data.user_id,
        bus_id=data.bus_id,
        seat_number=data.seat_number,
        passenger_name=data.passenger_name,
        passenger_age=data.passenger_age,
        journey_date=data.journey_date,
        booking_status="CONFIRMED"
    )

    db.add(booking)

    # Remove temporary lock
    db.delete(seat_lock)

    db.commit()
    db.refresh(booking)

    db.close()

    return {
        "success": True,
        "booking_id": booking.id,
        "message": "Ticket booked successfully"
    }

@app.get("/booked-seats/{bus_id}")
def get_booked_seats(
    bus_id: int,
    journey_date: str
):

    db = SessionLocal()

    # Delete expired locks
    db.query(SeatLock).filter(
        SeatLock.expires_at < datetime.now()
    ).delete()

    db.commit()

    bookings = db.query(Booking).filter(
        Booking.bus_id == bus_id,
        Booking.journey_date == journey_date,
        Booking.booking_status == "CONFIRMED"
    ).all()

    locks = db.query(SeatLock).filter(
        SeatLock.bus_id == bus_id,
        SeatLock.journey_date == journey_date,
        SeatLock.status == "LOCKED",
        SeatLock.expires_at > datetime.now()
    ).all()

    booked = []

    for booking in bookings:
        booked.append({
            "seat_number": booking.seat_number,
            "status": "BOOKED"
        })

    for lock in locks:
        booked.append({
            "seat_number": lock.seat_number,
            "status": "LOCKED"
        })

    db.close()

    return booked

@app.post("/lock-seats")
def lock_seats(data: SeatLockRequest):

    db = SessionLocal()

    # Delete expired locks
    db.query(SeatLock).filter(
        SeatLock.expires_at < datetime.now()
    ).delete()

    db.commit()

    for seat in data.seats:

        booking = db.query(Booking).filter(
            Booking.bus_id == data.bus_id,
            Booking.journey_date == data.journey_date,
            Booking.seat_number == seat,
            Booking.booking_status == "CONFIRMED"
        ).first()

        if booking:

            db.close()

            return {
                "success": False,
                "message": f"Seat {seat} already booked"
            }

        lock = db.query(SeatLock).filter(
            SeatLock.bus_id == data.bus_id,
            SeatLock.journey_date == data.journey_date,
            SeatLock.seat_number == seat,
            SeatLock.status == "LOCKED",
            SeatLock.expires_at > datetime.now()
        ).first()

        if lock and lock.user_id != data.user_id:

            db.close()

            return {
                "success": False,
                "message": f"Seat {seat} temporarily locked"
            }

    expires = datetime.now() + timedelta(minutes=10)

    for seat in data.seats:

        existing = db.query(SeatLock).filter(
            SeatLock.user_id == data.user_id,
            SeatLock.bus_id == data.bus_id,
            SeatLock.journey_date == data.journey_date,
            SeatLock.seat_number == seat
        ).first()

        if existing:

            existing.locked_at = datetime.now()
            existing.expires_at = expires
            existing.status = "LOCKED"

        else:

            db.add(
                SeatLock(
                    user_id=data.user_id,
                    bus_id=data.bus_id,
                    seat_number=seat,
                    journey_date=data.journey_date,
                    locked_at=datetime.now(),
                    expires_at=expires,
                    status="LOCKED"
                )
            )

    db.commit()

    db.close()

    return {
        "success": True,
        "message": "Seats locked successfully",
        "expires_in": 600
    }

@app.post("/release-seats")
def release_seats(data: ReleaseSeatRequest):

    db = SessionLocal()

    db.query(SeatLock).filter(
        SeatLock.user_id == data.user_id,
        SeatLock.bus_id == data.bus_id,
        SeatLock.journey_date == data.journey_date,
        SeatLock.status == "LOCKED"
    ).delete()

    db.commit()

    db.close()

    return {
        "success": True,
        "message": "Seat lock released"
    }

@app.get("/my-bookings/{user_id}")
def my_bookings(user_id: int):

    db = SessionLocal()

    bookings = db.query(Booking).filter(
        Booking.user_id == user_id
    ).all()

    result = []

    for booking in bookings:

        bus = db.query(Bus).filter(
            Bus.id == booking.bus_id
        ).first()

        result.append({
            "booking_id": booking.id,
            "bus_name": bus.bus_name if bus else "",
            "source": bus.source if bus else "",
            "destination": bus.destination if bus else "",
            "journey_date": booking.journey_date,
            "seat_number": booking.seat_number,
            "passenger_name": booking.passenger_name,
            "passenger_age": booking.passenger_age,
            "status": booking.booking_status
        })

    db.close()

    return result

@app.put("/cancel-booking/{booking_id}")
def cancel_booking(booking_id: int):

    db = SessionLocal()

    booking = db.query(Booking).filter(
        Booking.id == booking_id
    ).first()

    if not booking:
        db.close()
        return {
            "success": False,
            "message": "Booking not found"
        }

    booking.booking_status = "CANCELLED"

    db.commit()

    db.close()

    return {
        "success": True,
        "message": "Booking cancelled successfully"
    }

@app.post("/admin/add-bus")
def add_bus(data: BusCreate):

    db = SessionLocal()

    stops = [
        stop.strip()
        for stop in data.intermediate_stops.split(",")
        if stop.strip()
    ]

    distances = [
        distance.strip()
        for distance in data.stop_distances.split(",")
        if distance.strip()
    ]

    if len(stops) != len(distances):

        db.close()

        return {
            "success": False,
            "message": "Stops and distances count mismatch"
        }

    new_bus = Bus(
    bus_name=data.bus_name,
    bus_number=data.bus_number,
    source=data.source,
    destination=data.destination,
    departure_time=data.departure_time,
    arrival_time=data.arrival_time,
    fare=data.fare,
    total_seats=data.total_seats,
    total_route_distance=data.total_route_distance
)

    db.add(new_bus)
    db.commit()
    db.refresh(new_bus)

    order = 1

    source_stop = BusStop(
        bus_id=new_bus.id,
        stop_name=data.source,
        stop_order=order,
        distance_from_source=0
    )

    db.add(source_stop)

    order += 1

    for stop, distance in zip(stops, distances):

        stop_record = BusStop(
            bus_id=new_bus.id,
            stop_name=stop,
            stop_order=order,
            distance_from_source=int(distance)
        )

        db.add(stop_record)

        order += 1

    destination_distance = data.total_route_distance

    destination_stop = BusStop(
        bus_id=new_bus.id,
        stop_name=data.destination,
        stop_order=order,
        distance_from_source=destination_distance
    )

    db.add(destination_stop)

    db.commit()

    db.close()

    return {
        "success": True,
        "message": "Bus added successfully"
    }

@app.get("/admin/buses")
def get_all_buses():

    db = SessionLocal()

    buses = db.query(Bus).all()

    result = []

    for bus in buses:
        result.append({
            "id": bus.id,
            "bus_name": bus.bus_name,
            "bus_number": bus.bus_number,
            "source": bus.source,
            "destination": bus.destination,
            "fare": bus.fare
        })

    db.close()

    return result

@app.delete("/admin/delete-bus/{bus_id}")
def delete_bus(bus_id: int):

    db = SessionLocal()

    bus = db.query(Bus).filter(
        Bus.id == bus_id
    ).first()

    if not bus:

        db.close()

        return {
            "success": False,
            "message": "Bus not found"
        }

    db.delete(bus)
    db.commit()

    db.close()

    return {
        "success": True,
        "message": "Bus deleted successfully"
    }

@app.get("/admin/bookings")
def admin_bookings():

    db = SessionLocal()

    bookings = db.query(Booking).all()

    result = []

    for booking in bookings:

        bus = db.query(Bus).filter(
            Bus.id == booking.bus_id
        ).first()

        result.append({
            "booking_id": booking.id,
            "passenger_name": booking.passenger_name,
            "seat_number": booking.seat_number,
            "journey_date": booking.journey_date,
            "booking_status": booking.booking_status,
            "bus_name": bus.bus_name if bus else ""
        })

    db.close()

    return result

@app.get("/admin/stats")
def admin_stats():

    db = SessionLocal()

    total_users = db.query(User).count()
    total_buses = db.query(Bus).count()

    bookings = db.query(Booking).filter(
        Booking.booking_status == "CONFIRMED"
    ).all()

    total_bookings = len(bookings)

    total_revenue = 0

    for booking in bookings:
        bus = db.query(Bus).filter(
            Bus.id == booking.bus_id
        ).first()

        if bus:
            total_revenue += bus.fare

    db.close()

    return {
        "total_users": total_users,
        "total_buses": total_buses,
        "total_bookings": total_bookings,
        "total_revenue": total_revenue
    }

@app.get("/admin/bus/{bus_id}")
def get_bus(bus_id: int):

    db = SessionLocal()

    bus = db.query(Bus).filter(
        Bus.id == bus_id
    ).first()

    db.close()

    if not bus:
        return {
            "success": False,
            "message": "Bus not found"
        }

    return {
        "id": bus.id,
        "bus_name": bus.bus_name,
        "bus_number": bus.bus_number,
        "source": bus.source,
        "destination": bus.destination,
        "departure_time": bus.departure_time,
        "arrival_time": bus.arrival_time,
        "fare": bus.fare,
        "total_seats": bus.total_seats
    }

@app.put("/admin/update-bus/{bus_id}")
def update_bus(
    bus_id: int,
    data: BusCreate
):

    db = SessionLocal()

    bus = db.query(Bus).filter(
        Bus.id == bus_id
    ).first()

    if not bus:

        db.close()

        return {
            "success": False,
            "message": "Bus not found"
        }

    bus.bus_name = data.bus_name
    bus.bus_number = data.bus_number
    bus.source = data.source
    bus.destination = data.destination
    bus.departure_time = data.departure_time
    bus.arrival_time = data.arrival_time
    bus.fare = data.fare
    bus.total_seats = data.total_seats

    db.commit()

    db.close()

    return {
        "success": True,
        "message": "Bus updated successfully"
    }

@app.put("/update-profile/{user_id}")
def update_profile(
    user_id: int,
    data: UpdateProfileRequest
):

    db = SessionLocal()

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:

        db.close()

        return {
            "success": False,
            "message": "User not found"
        }

    user.full_name = data.full_name
    user.email = data.email
    user.phone = data.phone

    db.commit()

    db.close()

    return {
        "success": True,
        "message": "Profile updated successfully"
    }

@app.put("/forgot-password")
def forgot_password(
    data: ForgotPasswordRequest
):

    db = SessionLocal()

    user = db.query(User).filter(
        User.email == data.email
    ).first()

    if not user:

        db.close()

        return {
            "success": False,
            "message": "Email not found"
        }

    user.password_hash = data.new_password

    db.commit()

    db.close()

    return {
        "success": True,
        "message": "Password updated successfully"
    }

@app.put("/change-password/{user_id}")
def change_password(
    user_id: int,
    data: ChangePasswordRequest
):

    db = SessionLocal()

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:

        db.close()

        return {
            "success": False,
            "message": "User not found"
        }

    if user.password_hash != data.old_password:

        db.close()

        return {
            "success": False,
            "message": "Old password is incorrect"
        }

    user.password_hash = data.new_password

    db.commit()

    db.close()

    return {
        "success": True,
        "message": "Password changed successfully"
    }
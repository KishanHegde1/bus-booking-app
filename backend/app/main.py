from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from .database import get_db
from .models import Bus, User, Booking, BusStop, SeatLock
from .qr_utils import generate_secure_token
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


def _clean_csv_values(value: str):
    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


def _clean_seats(seats):
    cleaned = []

    for seat in seats:
        seat_value = str(seat).strip()

        if seat_value and seat_value not in cleaned:
            cleaned.append(seat_value)

    return cleaned


def _parse_route_stops(data: BusCreate):
    if not data.source.strip() or not data.destination.strip():
        return None, "Source and destination are required"

    if data.source.strip().lower() == data.destination.strip().lower():
        return None, "Source and destination cannot be same"

    if data.total_route_distance <= 0:
        return None, "Total route distance must be greater than zero"

    if data.fare <= 0:
        return None, "Fare must be greater than zero"

    if data.total_seats <= 0:
        return None, "Total seats must be greater than zero"

    stops = _clean_csv_values(data.intermediate_stops)
    distance_values = _clean_csv_values(data.stop_distances)

    if len(stops) != len(distance_values):
        return None, "Stops and distances count mismatch"

    parsed_stops = []
    previous_distance = 0

    for stop, distance_value in zip(stops, distance_values):
        try:
            distance = int(distance_value)
        except ValueError:
            return None, f"Invalid distance for stop {stop}"

        if distance <= previous_distance:
            return None, "Stop distances must be in increasing order"

        if distance >= data.total_route_distance:
            return None, "Intermediate stop distance must be less than total route distance"

        parsed_stops.append((stop, distance))
        previous_distance = distance

    return parsed_stops, None


def _add_bus_stops(db: Session, bus_id: int, data: BusCreate, parsed_stops):
    order = 1

    db.add(
        BusStop(
            bus_id=bus_id,
            stop_name=data.source.strip(),
            stop_order=order,
            distance_from_source=0
        )
    )

    order += 1

    for stop, distance in parsed_stops:
        db.add(
            BusStop(
                bus_id=bus_id,
                stop_name=stop,
                stop_order=order,
                distance_from_source=distance
            )
        )

        order += 1

    db.add(
        BusStop(
            bus_id=bus_id,
            stop_name=data.destination.strip(),
            stop_order=order,
            distance_from_source=data.total_route_distance
        )
    )


def _get_ordered_stops(db: Session, bus_id: int):
    return db.query(BusStop).filter(
        BusStop.bus_id == bus_id
    ).order_by(
        BusStop.stop_order
    ).all()


def _bus_route_fields(db: Session, bus: Bus):
    stops = _get_ordered_stops(db, bus.id)
    intermediate_stops = stops[1:-1] if len(stops) > 2 else []

    return {
        "total_route_distance": bus.total_route_distance,
        "intermediate_stops": ",".join(
            stop.stop_name or ""
            for stop in intermediate_stops
        ),
        "stop_distances": ",".join(
            str(stop.distance_from_source)
            for stop in intermediate_stops
        )
    }


def _calculate_journey(db: Session, bus: Bus, source: str, destination: str):
    if not source or not destination:
        return None

    if not bus.total_route_distance or bus.total_route_distance <= 0:
        return None

    if bus.fare is None:
        return None

    source_name = source.strip().lower()
    destination_name = destination.strip().lower()

    if source_name == destination_name:
        return None

    stops = _get_ordered_stops(db, bus.id)
    source_stop = None
    destination_stop = None

    for stop in stops:
        stop_name = (stop.stop_name or "").strip().lower()

        if stop_name == source_name:
            source_stop = stop

        if stop_name == destination_name:
            destination_stop = stop

    if not stops and (
        (bus.source or "").strip().lower() == source_name and
        (bus.destination or "").strip().lower() == destination_name
    ):
        return {
            "fare": round(bus.fare),
            "journey_distance": bus.total_route_distance
        }

    if not source_stop or not destination_stop:
        return None

    if source_stop.stop_order is None or destination_stop.stop_order is None:
        return None

    if source_stop.stop_order >= destination_stop.stop_order:
        return None

    if (
        source_stop.distance_from_source is None or
        destination_stop.distance_from_source is None
    ):
        return None

    journey_distance = (
        destination_stop.distance_from_source -
        source_stop.distance_from_source
    )

    if journey_distance <= 0:
        return None

    calculated_fare = round(
        (
            journey_distance /
            bus.total_route_distance
        ) * bus.fare
    )

    return {
        "fare": calculated_fare,
        "journey_distance": journey_distance
    }


def _delete_expired_locks(db: Session):
    db.query(SeatLock).filter(
        SeatLock.expires_at < datetime.now()
    ).delete(synchronize_session=False)


@app.get("/")
def home():
    return {
        "message": "BUS APP Backend Running"
    }


@app.get("/buses")
def get_buses(db: Session = Depends(get_db)):

    buses = db.query(Bus).all()

    result = []

    for bus in buses:
        result.append({
            "id": bus.id,
            "bus_name": bus.bus_name,
            "bus_number": bus.bus_number,
            "source": bus.source,
            "destination": bus.destination,
            "departure_time": bus.departure_time,
            "arrival_time": bus.arrival_time,
            "fare": bus.fare,
            "total_seats": bus.total_seats,
            "total_route_distance": bus.total_route_distance
        })

    return result


@app.post("/register")
def register(
    user: UserRegister,
    db: Session = Depends(get_db)
):

    existing_user = db.query(User).filter(
        User.email == user.email
    ).first()

    if existing_user:
        return {
            "success": False,
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

    return {
        "success": True,
        "message": "User registered successfully"
    }

@app.post("/login")
def login(
    user: UserLogin,
    db: Session = Depends(get_db)
):

    existing_user = db.query(User).filter(
        User.email == user.email
    ).first()

    if not existing_user:
        return {
            "success": False,
            "message": "User not found"
        }

    if existing_user.password_hash != user.password:
        return {
            "success": False,
            "message": "Invalid password"
        }

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
    destination: str,
    db: Session = Depends(get_db)
):

    buses = db.query(Bus).all()

    result = []

    for bus in buses:
        journey = _calculate_journey(
            db,
            bus,
            source,
            destination
        )

        if journey:
            result.append({
                "id": bus.id,
                "bus_name": bus.bus_name,
                "bus_number": bus.bus_number,
                "source": source,
                "destination": destination,
                "departure_time": str(bus.departure_time),
                "arrival_time": str(bus.arrival_time),
                "fare": journey["fare"],
                "journey_distance": journey["journey_distance"],
                "total_seats": bus.total_seats
            })

    return result

@app.post("/book-ticket")
def book_ticket(
    data: BookingRequest,
    db: Session = Depends(get_db)
):

    seat_number = data.seat_number.strip()

    if not seat_number:
        return {
            "success": False,
            "message": "Seat number is required"
        }

    user = db.query(User).filter(
        User.id == data.user_id
    ).first()

    if not user:
        return {
            "success": False,
            "message": "User not found"
        }

    bus = db.query(Bus).filter(
        Bus.id == data.bus_id
    ).first()

    if not bus:
        return {
            "success": False,
            "message": "Bus not found"
        }

    fare = data.fare

    if bool(data.source) != bool(data.destination):
        return {
            "success": False,
            "message": "Source and destination are required together"
        }

    if data.source and data.destination:
        journey = _calculate_journey(
            db,
            bus,
            data.source,
            data.destination
        )

        if not journey:
            return {
                "success": False,
                "message": "Invalid journey route"
            }

        fare = journey["fare"]

    if fare <= 0:
        return {
            "success": False,
            "message": "Invalid fare"
        }

    # Convert journey date once
    try:
       journey_date = datetime.strptime(
           data.journey_date,
           "%Y-%m-%d"
        ).date()
    except ValueError:
        return {
            "success": False,
            "message": "Invalid journey date"
        }

    # Check if seat is already permanently booked
    existing_booking = db.query(Booking).filter(
        Booking.bus_id == data.bus_id,
        Booking.seat_number == seat_number,
        Booking.journey_date == journey_date,
        Booking.booking_status == "CONFIRMED"
    ).first()

    if existing_booking:
        return {
            "success": False,
            "message": "Seat already booked"
        }

    # Check whether this seat is locked by this user
    seat_lock = db.query(SeatLock).filter(
        SeatLock.user_id == data.user_id,
        SeatLock.bus_id == data.bus_id,
        SeatLock.seat_number == seat_number,
        SeatLock.journey_date == journey_date,
        SeatLock.status == "LOCKED",
        SeatLock.expires_at > datetime.now()
    ).first()

    if not seat_lock:
        return {
            "success": False,
            "message": "Seat lock expired. Please select seat again."
        }

    # Create Booking
    booking = Booking(
        user_id=data.user_id,
        bus_id=data.bus_id,
        seat_number=seat_number,
        passenger_name=data.passenger_name,
        passenger_age=data.passenger_age,
        journey_date=journey_date,
        fare=fare,
        booking_status="CONFIRMED"
    )

    db.add(booking)

    # Remove temporary lock
    db.delete(seat_lock)

    # Generate secure QR token
    booking.qr_code = generate_secure_token()

    # Default ticket status
    booking.ticket_status = "UNUSED"

    try:
       db.commit()
       db.refresh(booking)
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "message": str(e)
        }

    return {
        "success": True,
        "booking_id": booking.id,
        "qr_code": booking.qr_code,
        "ticket_status": booking.ticket_status,
        "message": "Ticket booked successfully"
    }

@app.get("/booked-seats/{bus_id}")
def get_booked_seats(
    bus_id: int,
    journey_date: str,
    db: Session = Depends(get_db)
):

    # Convert string to date
    try:
       journey_date = datetime.strptime(
           journey_date,
           "%Y-%m-%d"
       ).date()
    except ValueError:
        return []

    # Delete expired locks
    _delete_expired_locks(db)

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

    return booked

@app.post("/lock-seats")
def lock_seats(
    data: SeatLockRequest,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.id == data.user_id
    ).first()

    if not user:
        return {
            "success": False,
            "message": "User not found"
        }

    bus = db.query(Bus).filter(
        Bus.id == data.bus_id
    ).first()

    if not bus:
        return {
            "success": False,
            "message": "Bus not found"
        }

    seats = _clean_seats(data.seats)

    try:
       journey_date = datetime.strptime(
           data.journey_date,
           "%Y-%m-%d"
        ).date()
    except ValueError:
        return {
            "success": False,
            "message": "Invalid journey date"
        }

    if not seats:
        return {
            "success": False,
            "message": "No seats selected"
        }

    # Delete expired locks
    _delete_expired_locks(db)

    db.commit()

    for seat in seats:

        booking = db.query(Booking).filter(
            Booking.bus_id == data.bus_id,
            Booking.journey_date == journey_date,
            Booking.seat_number == seat,
            Booking.booking_status == "CONFIRMED"
        ).first()

        if booking:

            return {
                "success": False,
                "message": f"Seat {seat} already booked"
            }

        lock = db.query(SeatLock).filter(
            SeatLock.bus_id == data.bus_id,
            SeatLock.journey_date == journey_date,
            SeatLock.seat_number == seat,
            SeatLock.status == "LOCKED",
            SeatLock.expires_at > datetime.now()
        ).first()

        if lock and lock.user_id != data.user_id:

            return {
                "success": False,
                "message": f"Seat {seat} temporarily locked"
            }

    expires = datetime.now() + timedelta(minutes=10)

    for seat in seats:

        existing = db.query(SeatLock).filter(
            SeatLock.user_id == data.user_id,
            SeatLock.bus_id == data.bus_id,
            SeatLock.journey_date == journey_date,
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
                    journey_date=journey_date,
                    locked_at=datetime.now(),
                    expires_at=expires,
                    status="LOCKED"
                )
            )

    try:
        db.commit()

    except Exception as e:
        db.rollback()

        import traceback
        traceback.print_exc()

        return {
            "success": False,
            "message": str(e)
        }

    return {
        "success": True,
        "message": "Seats locked successfully",
        "expires_in": 600
    }

@app.post("/release-seats")
def release_seats(
    data: ReleaseSeatRequest,
    db: Session = Depends(get_db)
):
    # Convert incoming string to Python date
    try:
       journey_date = datetime.strptime(
           data.journey_date,
           "%Y-%m-%d"
        ).date()
    except ValueError:
        return {
            "success": False,
            "message": "Invalid journey date"
        }


    query = db.query(SeatLock).filter(
        SeatLock.user_id == data.user_id,
        SeatLock.bus_id == data.bus_id,
        SeatLock.journey_date == journey_date,
        SeatLock.status == "LOCKED"
    )

    seats = _clean_seats(data.seats or [])

    if seats:
        query = query.filter(
            SeatLock.seat_number.in_(seats)
        )

    query.delete(synchronize_session=False)

    db.commit()

    return {
        "success": True,
        "message": "Seat lock released"
    }

@app.get("/my-bookings/{user_id}")
def my_bookings(
    user_id: int,
    db: Session = Depends(get_db)
):

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
    "journey_date": booking.journey_date.strftime("%Y-%m-%d"),
    "seat_number": booking.seat_number,
    "passenger_name": booking.passenger_name,
    "passenger_age": booking.passenger_age,
    "status": booking.booking_status,

    # QR Ticket
    "qr_code": booking.qr_code,
    "ticket_status": booking.ticket_status,
})
        
    return result

@app.put("/cancel-booking/{booking_id}")
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db)
):

    booking = db.query(Booking).filter(
        Booking.id == booking_id
    ).first()

    if not booking:
        return {
            "success": False,
            "message": "Booking not found"
        }

    booking.booking_status = "CANCELLED"

    db.commit()

    return {
        "success": True,
        "message": "Booking cancelled successfully"
    }

@app.post("/admin/add-bus")
def add_bus(
    data: BusCreate,
    db: Session = Depends(get_db)
):

    parsed_stops, error = _parse_route_stops(data)

    if error:
        return {
            "success": False,
            "message": error
        }

    new_bus = Bus(
        bus_name=data.bus_name,
        bus_number=data.bus_number,
        source=data.source.strip(),
        destination=data.destination.strip(),
        departure_time=data.departure_time,
        arrival_time=data.arrival_time,
        fare=data.fare,
        total_seats=data.total_seats,
        total_route_distance=data.total_route_distance
    )

    db.add(new_bus)
    db.flush()
    _add_bus_stops(
        db,
        new_bus.id,
        data,
        parsed_stops
    )

    db.commit()

    return {
        "success": True,
        "message": "Bus added successfully"
    }

@app.get("/admin/buses")
def get_all_buses(db: Session = Depends(get_db)):

    buses = db.query(Bus).all()

    result = []

    for bus in buses:
        result.append({
            "id": bus.id,
            "bus_name": bus.bus_name,
            "bus_number": bus.bus_number,
            "source": bus.source,
            "destination": bus.destination,
            "departure_time": bus.departure_time,
            "arrival_time": bus.arrival_time,
            "fare": bus.fare,
            "total_seats": bus.total_seats,
            "total_route_distance": bus.total_route_distance
        })

    return result

@app.delete("/admin/delete-bus/{bus_id}")
def delete_bus(
    bus_id: int,
    db: Session = Depends(get_db)
):

    bus = db.query(Bus).filter(
        Bus.id == bus_id
    ).first()

    if not bus:

        return {
            "success": False,
            "message": "Bus not found"
        }

    db.query(BusStop).filter(
        BusStop.bus_id == bus_id
    ).delete(synchronize_session=False)

    db.query(SeatLock).filter(
        SeatLock.bus_id == bus_id
    ).delete(synchronize_session=False)

    db.delete(bus)
    db.commit()

    return {
        "success": True,
        "message": "Bus deleted successfully"
    }

@app.get("/admin/bookings")
def admin_bookings(db: Session = Depends(get_db)):

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
            "journey_date": booking.journey_date.strftime("%Y-%m-%d"),
            "booking_status": booking.booking_status,
            "bus_name": bus.bus_name if bus else ""
        })

    return result

@app.get("/admin/stats")
def admin_stats(db: Session = Depends(get_db)):

    total_users = db.query(User).count()
    total_buses = db.query(Bus).count()

    bookings = db.query(Booking).filter(
        Booking.booking_status == "CONFIRMED"
    ).all()

    total_bookings = len(bookings)

    total_revenue = 0

    for booking in bookings:
       total_revenue += booking.fare

    return {
        "total_users": total_users,
        "total_buses": total_buses,
        "total_bookings": total_bookings,
        "total_revenue": total_revenue
    }

@app.get("/admin/bus/{bus_id}")
def get_bus(
    bus_id: int,
    db: Session = Depends(get_db)
):

    bus = db.query(Bus).filter(
        Bus.id == bus_id
    ).first()

    if not bus:
        return {
            "success": False,
            "message": "Bus not found"
        }

    route_fields = _bus_route_fields(db, bus)

    return {
        "id": bus.id,
        "bus_name": bus.bus_name,
        "bus_number": bus.bus_number,
        "source": bus.source,
        "destination": bus.destination,
        "departure_time": bus.departure_time,
        "arrival_time": bus.arrival_time,
        "fare": bus.fare,
        "total_seats": bus.total_seats,
        **route_fields
    }

@app.put("/admin/update-bus/{bus_id}")
def update_bus(
    bus_id: int,
    data: BusCreate,
    db: Session = Depends(get_db)
):

    bus = db.query(Bus).filter(
        Bus.id == bus_id
    ).first()

    if not bus:

        return {
            "success": False,
            "message": "Bus not found"
        }

    parsed_stops, error = _parse_route_stops(data)

    if error:
        return {
            "success": False,
            "message": error
        }

    bus.bus_name = data.bus_name
    bus.bus_number = data.bus_number
    bus.source = data.source.strip()
    bus.destination = data.destination.strip()
    bus.departure_time = data.departure_time
    bus.arrival_time = data.arrival_time
    bus.fare = data.fare
    bus.total_seats = data.total_seats
    bus.total_route_distance = data.total_route_distance

    db.query(BusStop).filter(
        BusStop.bus_id == bus_id
    ).delete(synchronize_session=False)

    _add_bus_stops(
        db,
        bus_id,
        data,
        parsed_stops
    )

    db.commit()

    return {
        "success": True,
        "message": "Bus updated successfully"
    }

@app.put("/update-profile/{user_id}")
def update_profile(
    user_id: int,
    data: UpdateProfileRequest,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:

        return {
            "success": False,
            "message": "User not found"
        }

    existing_email = db.query(User).filter(
        User.email == data.email,
        User.id != user_id
    ).first()

    if existing_email:
        return {
            "success": False,
            "message": "Email already registered"
        }

    user.full_name = data.full_name
    user.email = data.email
    user.phone = data.phone

    db.commit()

    return {
        "success": True,
        "message": "Profile updated successfully"
    }

@app.put("/forgot-password")
def forgot_password(
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.email == data.email
    ).first()

    if not user:

        return {
            "success": False,
            "message": "Email not found"
        }

    user.password_hash = data.new_password

    db.commit()

    return {
        "success": True,
        "message": "Password updated successfully"
    }

@app.put("/change-password/{user_id}")
def change_password(
    user_id: int,
    data: ChangePasswordRequest,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:

        return {
            "success": False,
            "message": "User not found"
        }

    if user.password_hash != data.old_password:

        return {
            "success": False,
            "message": "Old password is incorrect"
        }

    user.password_hash = data.new_password

    db.commit()

    return {
        "success": True,
        "message": "Password changed successfully"
    }

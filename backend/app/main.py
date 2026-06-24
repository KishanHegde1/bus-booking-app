from fastapi import FastAPI
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Bus, User, Booking, BusStop

from .schemas import (
    UserRegister,
    UserLogin,
    BookingRequest,
    BusCreate,
    UpdateProfileRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest
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
def search_buses(source: str, destination: str):

    db = SessionLocal()

    buses = db.query(Bus).filter(
        Bus.source.ilike(f"%{source}%"),
        Bus.destination.ilike(f"%{destination}%")
    ).all()

    result = []

    for bus in buses:
        result.append({
            "id": bus.id,
            "bus_name": bus.bus_name,
            "bus_number": bus.bus_number,
            "source": bus.source,
            "destination": bus.destination,
            "departure_time": str(bus.departure_time),
            "arrival_time": str(bus.arrival_time),
            "fare": bus.fare,
            "total_seats": bus.total_seats
        })

    db.close()

    return result
@app.post("/book-ticket")
def book_ticket(data: BookingRequest):

    db = SessionLocal()

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

    bookings = db.query(Booking).filter(
        Booking.bus_id == bus_id,
        Booking.journey_date == journey_date,
        Booking.booking_status == "CONFIRMED"
    ).all()

    seats = []

    for booking in bookings:
        seats.append(
            booking.seat_number
        )

    db.close()

    return seats
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

    new_bus = Bus(
        bus_name=data.bus_name,
        bus_number=data.bus_number,
        source=data.source,
        destination=data.destination,
        departure_time=data.departure_time,
        arrival_time=data.arrival_time,
        fare=data.fare,
        total_seats=data.total_seats
    )

    db.add(new_bus)
    db.commit()
    db.refresh(new_bus)

    order = 1

    # Source Stop
    source_stop = BusStop(
        bus_id=new_bus.id,
        stop_name=data.source,
        stop_order=order
    )

    db.add(source_stop)

    order += 1

    # Intermediate Stops
    if data.intermediate_stops.strip():

        stops = data.intermediate_stops.split(",")

        for stop in stops:

            stop_record = BusStop(
                bus_id=new_bus.id,
                stop_name=stop.strip(),
                stop_order=order
            )

            db.add(stop_record)

            order += 1

    # Destination Stop
    destination_stop = BusStop(
        bus_id=new_bus.id,
        stop_name=data.destination,
        stop_order=order
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
from pydantic import BaseModel
from typing import Optional

class UserRegister(BaseModel):
    full_name: str
    email: str
    phone: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str

class BookingRequest(BaseModel):
    user_id: int
    bus_id: int
    passenger_name: str
    passenger_age: int
    seat_number: str
    journey_date: str

    fare: float
    source: Optional[str] = None
    destination: Optional[str] = None
    
class BusCreate(BaseModel):
    bus_name: str
    bus_number: str
    source: str
    destination: str
    intermediate_stops: str
    stop_distances: str
    departure_time: str
    arrival_time: str
    fare: float
    total_seats: int
    total_route_distance: int
    
class UpdateProfileRequest(BaseModel):
    full_name: str
    email: str
    phone: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
    
class ForgotPasswordRequest(BaseModel):
    email: str
    new_password: str

class SeatLockRequest(BaseModel):
    user_id: int
    bus_id: int
    journey_date: str
    seats: list[str]


class ReleaseSeatRequest(BaseModel):
    user_id: int
    bus_id: int
    journey_date: str
    seats: Optional[list[str]] = None


class QRCodeVerifyRequest(BaseModel):
    qr_code: str


class MarkBoardedRequest(BaseModel):
    booking_id: int


class DashboardResponse(BaseModel):
    success: bool
    conductor_name: str
    conductor_id: int
    tickets_verified: int
    passengers_boarded: int
    invalid_tickets: int
    already_used: int
    last_sync: str
    today_date: str


class HistoryResponse(BaseModel):
    booking_id: int
    passenger_name: str
    seat_number: str
    journey_date: str
    bus_name: str
    bus_number: str
    status: str
    scanned_time: str


class TripInformationResponse(BaseModel):
    bus_name: str
    bus_number: str
    source: str
    destination: str
    departure_time: str
    arrival_time: str
    total_seats: int
    booked_seats: int
    available_seats: int
    occupancy_percentage: float

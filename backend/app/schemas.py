from pydantic import BaseModel

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
class BusCreate(BaseModel):
    bus_name: str
    bus_number: str
    source: str
    destination: str
    departure_time: str
    arrival_time: str
    fare: float
    total_seats: int
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
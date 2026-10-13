from pydantic import BaseModel


class DonationCreate(BaseModel):
    """Input model used by both the web and REST interfaces."""

    food_type: str
    quantity: str
    pickup_address: str
    pickup_deadline: str
    description: str = ''

from fastapi import FastAPI, Form, HTTPException

from fastapi.responses import HTMLResponse, RedirectResponse

from models import DonationCreate

from services import service

from views import page

app = FastAPI(title='FoodRescue', version='1.0')

# ---------- MVC Pattern: Controllers ----------

# These FastAPI route handlers act as Controllers. They accept interface input,

# call the shared DonationService core logic, and select/return a View response.

@app.get('/', response_class=HTMLResponse)

def home():

    return page(

        'FoodRescue',

        '<h1>FoodRescue</h1>'

        '<p>Connect surplus food from businesses with registered charities.</p>'

        '<p><a href="/donations/new">Create a donation</a> or '

        '<a href="/donations">view available donations</a>.</p>'

    )

@app.get('/donations/new', response_class=HTMLResponse)

def new_form():

    return page(

        'Donate',

        '''<h1>Create Donation</h1>

        <form method="post" action="/donations">

        <label>Food type</label>

        <input name="food_type" required>

        <label>Quantity</label>

        <input name="quantity" required>

        <label>Pickup address</label>

        <input name="pickup_address" required>

        <label>Pickup deadline</label>

        <input name="pickup_deadline"

               placeholder="2026-10-20 20:00"

               required>

        <label>Description</label>

        <textarea name="description"></textarea>

        <button>Create Donation</button>

        </form>'''

    )

@app.post('/donations')

def create_web(

    food_type: str = Form(...),

    quantity: str = Form(...),

    pickup_address: str = Form(...),

    pickup_deadline: str = Form(...),

    description: str = Form('')

):

    donation = DonationCreate(

        food_type=food_type,

        quantity=quantity,

        pickup_address=pickup_address,

        pickup_deadline=pickup_deadline,

        description=description

    )

    service().create_donation(donation)

    return RedirectResponse('/donations', status_code=303)

@app.get('/donations', response_class=HTMLResponse)

def list_web():

    # Web interface and REST interface intentionally use

    # the same DonationService method.

    items = service().get_available_donations()

    cards = []

    for x in items:

        location_link = ''

        if x.get('latitude') and x.get('longitude'):

            location_link = (

                f"<p><a href='https://www.google.com/maps/search/"

                f"?api=1&query={x['latitude']},{x['longitude']}' "

                f"target='_blank' rel='noopener noreferrer'>"

                f"📍 View Location</a></p>"

            )

        card = f"""<div class="card">

        <h3>{x['food_type']}</h3>

        <p>

        <b>Quantity:</b> {x['quantity']}<br>

        <b>Pickup:</b> {x['pickup_address']}<br>

        <b>Deadline:</b> {x['pickup_deadline']}

        </p>

        <p>{x.get('description', '')}</p>

        {location_link}

        <form method="post"

              action="/donations/{x['donation_id']}/reserve">

        <input name="charity_name"

               placeholder="Registered charity name"

               required>

        <button>Reserve</button>

        </form>

        </div>"""

        cards.append(card)

    cards_html = ''.join(cards) or '<p>No available donations.</p>'

    return page(

        'Available Donations',

        '<h1>Available Donations</h1>' + cards_html

    )

@app.post('/donations/{donation_id}/reserve')

def reserve_web(

    donation_id: str,

    charity_name: str = Form(...)

):

    try:

        service().reserve_donation(

            donation_id,

            charity_name

        )

    except ValueError as e:

        raise HTTPException(409, str(e))

    return RedirectResponse(

        '/donations',

        status_code=303

    )

@app.get('/donations/manage', response_class=HTMLResponse)

def manage_web():

    items = sorted(

        service().get_all_donations(),

        key=lambda x: x.get('created_at', ''),

        reverse=True

    )

    cards = []

    for x in items:

        status = x.get('status', 'UNKNOWN')

        reserved = x.get('reserved_by') or '—'

        actions = ''

        if status == 'AVAILABLE':

            actions = (

                f"<form method='post' "

                f"action='/donations/{x['donation_id']}/expire'>"

                f"<button>Mark Expired</button>"

                f"</form>"

            )

        elif status == 'RESERVED':

            actions = (

                f"<form method='post' "

                f"action='/donations/{x['donation_id']}/complete'>"

                f"<button>Mark Completed</button>"

                f"</form>"

                f"<form method='post' "

                f"action='/donations/{x['donation_id']}/expire'>"

                f"<button>Mark Expired</button>"

                f"</form>"

            )

        location_link = ''

        if x.get('latitude') and x.get('longitude'):

            location_link = (

                f"<p><a href='https://www.google.com/maps/search/"

                f"?api=1&query={x['latitude']},{x['longitude']}' "

                f"target='_blank' rel='noopener noreferrer'>"

                f"📍 View Location</a></p>"

            )

        card = (

            f"<div class='card'>"

            f"<h3>{x.get('food_type', 'Donation')}</h3>"

            f"<p>"

            f"<span class='status'>{status}</span><br>"

            f"<b>Quantity:</b> {x.get('quantity', '')}<br>"

            f"<b>Pickup:</b> {x.get('pickup_address', '')}<br>"

            f"<b>Deadline:</b> {x.get('pickup_deadline', '')}<br>"

            f"<b>Reserved by:</b> {reserved}"

            f"</p>"

            f"{location_link}"

            f"<div class='actions'>"

            f"{actions}"

            f"</div>"

            f"</div>"

        )

        cards.append(card)

    cards_html = ''.join(cards) or '<p>No donations yet.</p>'

    return page(

        'Manage Donations',

        '<h1>Manage Donations</h1>'

        '<p>View every donation and move valid donations '

        'through their lifecycle.</p>'

        + cards_html

    )

@app.post('/donations/{donation_id}/complete')

def complete_web(donation_id: str):

    try:

        service().complete_donation(donation_id)

    except ValueError as e:

        raise HTTPException(409, str(e))

    return RedirectResponse(

        '/donations/manage',

        status_code=303

    )

@app.post('/donations/{donation_id}/expire')

def expire_web(donation_id: str):

    try:

        service().expire_donation(donation_id)

    except ValueError as e:

        raise HTTPException(409, str(e))

    return RedirectResponse(

        '/donations/manage',

        status_code=303

    )

# ---------- REST Interface ----------

@app.get('/api/donations')

def list_api():

    # Same core logic as GET /donations.

    # Availability logic is not duplicated.

    return service().get_available_donations()

@app.post('/api/donations', status_code=201)

def create_api(donation: DonationCreate):

    return service().create_donation(donation)

@app.post('/api/donations/{donation_id}/reserve')

def reserve_api(

    donation_id: str,

    charity_name: str

):

    try:

        return service().reserve_donation(

            donation_id,

            charity_name

        )

    except ValueError as e:

        raise HTTPException(409, str(e))

@app.post('/api/donations/{donation_id}/complete')

def complete_api(donation_id: str):

    try:

        return service().complete_donation(donation_id)

    except ValueError as e:

        raise HTTPException(409, str(e))

@app.post('/api/donations/{donation_id}/expire')

def expire_api(donation_id: str):

    try:

        return service().expire_donation(donation_id)

    except ValueError as e:

        raise HTTPException(409, str(e))
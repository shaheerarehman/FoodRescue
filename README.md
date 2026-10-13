# FoodRescue

Run from this directory:

1. Create/activate a virtual environment.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your own values.
4. Run `python create_table.py` once if the DynamoDB table does not exist.
5. Run `uvicorn app:app --reload`

## Module organization

- `app.py` - FastAPI web and REST controllers/routes.
- `views.py` - HTML view rendering.
- `models.py` - request/data models.
- `services.py` - shared application logic and Google geocoding integration.
- `repository.py` - DynamoDB persistence operations.
- `states.py` - State and Factory pattern implementations.
- `config.py` - environment configuration.

The HTML `GET /donations` route and REST `GET /api/donations` route both call `DonationService.get_available_donations()`, so the two interfaces share the same core implementation.
